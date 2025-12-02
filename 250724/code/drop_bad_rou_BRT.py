import pandas
import xml.etree.ElementTree as ET
import numpy as np

# 乱数シードを固定し、毎回同じ結果を生成
np.random.seed(0)

# --- 入力ファイル ---
df = pandas.read_csv('250724/data/try_BRT_matched.csv')
tree = ET.parse('250724/data/sunday_BRT_out_nodes.xml')

# --- 出力ファイル ---
rou_file_path = '250724/data/try_BRT_dropped.rou.xml'

# ETC2.0の普及率
ADAPT_RATE_TRUCK = 0.85
ADAPT_RATE_NORMAL = 0.30

# --- 1. 経路長情報の読み込み ---
root = tree.getroot()
dua = {}
for child in root:
    if child.tag == 'vehicle':
        id_val = child.attrib['id']
        route = child.find('route')
        if route is not None and 'routeLength' in route.attrib:
            dua[id_val] = route.get('routeLength')

# route_length列を追加
route_length_list = []
for i in range(len(df)):
    id_val = "t_" + df["rou_id"].iloc[i]
    route_length_list.append(float(dua[id_val]) if id_val in dua else -1)
df['route_length'] = route_length_list

# --- 2. route_lengthが500m以下を除外 ---
df_valid_trips = df[df['route_length'] > 500].copy()
print(f"元のトリップ数: {len(df)}")
print(f"500mより長い有効なトリップ数: {len(df_valid_trips)}")

# --- 3. サンプリング処理 ---
num_days = df_valid_trips['運行日'].nunique()
if num_days == 0:
    print("有効なデータが存在しません。")
    df_mini = pandas.DataFrame()
else:
    df_trucks = df_valid_trips[df_valid_trips['自動車の用途'] == 2]
    df_normal = df_valid_trips[df_valid_trips['自動車の用途'] != 2]

    num_truck_per_day = int(len(df_trucks) / num_days / ADAPT_RATE_TRUCK)
    num_normal_per_day = int(len(df_normal) / num_days / ADAPT_RATE_NORMAL)

    print(f"運行日数: {num_days}日")
    print(f"1日あたりトラック目標数: {num_truck_per_day}")
    print(f"1日あたり普通車目標数: {num_normal_per_day}")

    def sample_by_vehicle_id(df_source, target_trip_count):
        if df_source.empty or target_trip_count == 0:
            return pandas.DataFrame()
        vehicle_ids = df_source['運行ID1'].unique()
        np.random.shuffle(vehicle_ids)
        selected = []
        count = 0
        for vid in vehicle_ids:
            group = df_source[df_source['運行ID1'] == vid]
            selected.append(group)
            count += len(group)
            if count >= target_trip_count:
                break
        return pandas.concat(selected, ignore_index=True)

    df_sampled_trucks = sample_by_vehicle_id(df_trucks, num_truck_per_day)
    df_sampled_normal = sample_by_vehicle_id(df_normal, num_normal_per_day)
    df_mini = pandas.concat([df_sampled_trucks, df_sampled_normal], ignore_index=True)

    print(f"抽出合計: {len(df_mini)} (トラック: {len(df_sampled_trucks)}, 普通車: {len(df_sampled_normal)})")

# --- route_length統計確認 ---
if not df_mini.empty:
    print("\n--- route_length統計 ---")
    print(df_mini['route_length'].describe())
    if df_mini['route_length'].min() > 500:
        print("[確認OK] すべて500m超。")
    else:
        print("[警告] 500m以下のトリップが含まれます。")

# --- 4. rou.xml作成 ---
rou_root = ET.Element('routes')
ET.SubElement(rou_root, "vType", id="DEFAULT_VEHTYPE")
ET.SubElement(rou_root, "vType", id="truck", vClass="truck")

vtype_BUS = ET.SubElement(rou_root, 'vType')
vtype_BUS.set('id', 'BUS')
vtype_BUS.set('vClass', 'bus')
vtype_BUS.set('length', '12')
vtype_BUS.set('width', '2.5')
vtype_BUS.set('maxSpeed', '27')
vtype_BUS.set('accel', '2.0')
vtype_BUS.set('decel', '4.0')
vtype_BUS.set('sigma', '0.5')
vtype_BUS.set('color', '1,1,0')
vtype_BUS.set('personCapacity', '40')

bus_flow = ET.SubElement(rou_root, 'flow')
bus_flow.set('id', 'busflow_1')
bus_flow.set('type', 'BUS')
bus_flow.set('begin', '21600')
bus_flow.set('end', '86399')
bus_flow.set('line', 'line')
bus_flow.set('from', '128185375')
bus_flow.set('to', '128185375')
bus_flow.set('via', '447675894#1 447675894#1.32 -E19 -E18 -E17 -E16 -E16.17 -E15 -E14 E12 E12.154 E12.164 E13 1231325642#0 1231325642#0.343 1231325642#1 1231325642#2 1231325646#0 1231325646#0.55 1231325646#1 1231325646#2 1231325647 1185697574#0 1185697574#1 1185697574#2 1185697574#3 951329849#1 951329849#2 951329849#3 951328429#0 951328429#1 169920326#0 169920326#1 169920326#2 169920326#3 169920326#4 1231325655#0 1231325655#0.62 1231325655#0.62.56 1231325655#1 1231325655#2 1231325664#0 E51 E70 E70.449 28184296#9 28184616 28111409 28184603#1 -E70.140.315 41247903#4 1231325662#1.41 1231325661#1 951329843 951329843.64 1231325643#1 1231325643#2 447675894#1 447675894#1.32 -E19 -E18 -E17 -E16 -E16.17 -E15 -E14 E12 E12.154 E12.164')
bus_flow.set('period', '300.00')
bus_flow.set('arrivalLane', '2')
bus_flow.set('departLaneChangeProhibited', 'true')
bus_flow.set('arrivalLaneChangeProhibited', 'true')
bus_flow.set('arrivalLane', '2')
bus_flow.set('departLaneChangeProhibited', 'true')
bus_flow.set('arrivalLaneChangeProhibited', 'true')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_smartic3')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_sokaparkd')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketownd')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketown2d')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketown3d')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_ichigoparkd')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_techpoliced')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_toyonod')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_kasukabeaeond')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_kasukabeaeonu')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_toyonou')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_techpoliceu')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_ichigoparku')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketown3u')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketown2u')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_laketownu')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_sokaparku')
stop.set('until', '1')
stop = ET.SubElement(bus_flow, 'stop')
stop.set('busStop', 'bs_smartic3')
stop.set('until', '1')

    <flow id="busflow_1" type="BUS" begin="0" end="86399" line="line" from="128185375" to="128185375" via="447675894#1 447675894#1.32 -E19 -E18 -E17 -E16 -E16.17 -E15 -E14 E12 E12.154 E12.164 E13 1231325642#0 1231325642#0.343 1231325642#1 1231325642#2 1231325646#0 1231325646#0.55 1231325646#1 1231325646#2 1231325647 1185697574#0 1185697574#1 1185697574#2 1185697574#3 951329849#1 951329849#2 951329849#3 951328429#0 951328429#1 169920326#0 169920326#1 169920326#2 169920326#3 169920326#4 1231325655#0 1231325655#0.62 1231325655#0.62.56 1231325655#1 1231325655#2 1231325664#0 E51 E70 E70.449 28184296#9 28184616 28111409 28184603#1 -E70.140.315 41247903#4 1231325662#1.41 1231325661#1 951329843 951329843.64 1231325643#1 1231325643#2 447675894#1 447675894#1.32 -E19 -E18 -E17 -E16 -E16.17 -E15 -E14 E12 E12.154 E12.164" period="300.00" arrivalLane="2" departLaneChangeProhibited="true" arrivalLaneChangeProhibited="true">
        <!-- <stop busStop="bs_smartic" until="1"/> -->
        <stop busStop="bs_smartic3" until="1"/>
        <stop busStop="bs_sokaparkd" until="1"/>
        <stop busStop="bs_laketownd" until="1"/>
        <stop busStop="bs_laketown2d" until="1"/>
        <stop busStop="bs_laketown3d" until="1"/>
        <stop busStop="bs_ichigoparkd" until="1"/>
        <stop busStop="bs_techpoliced" until="1"/>
        <stop busStop="bs_toyonod" until="1"/>
        <stop busStop="bs_kasukabeaeond" until="1"/>
        <stop busStop="bs_kasukabeaeonu" until="1"/>
        <stop busStop="bs_toyonou" until="1"/>
        <stop busStop="bs_techpoliceu" until="1"/>
        <stop busStop="bs_ichigoparku" until="1"/>
        <stop busStop="bs_laketown3u" until="1"/>
        <stop busStop="bs_laketown2u" until="1"/>
        <stop busStop="bs_laketownu" until="1"/>
        <stop busStop="bs_sokaparku" until="1"/>
        <stop busStop="bs_smartic3" until="1"/>
    </flow>

# 出力トリップ生成
trips_temp = []
if not df_mini.empty:
    for i, row in df_mini.iterrows():
        # 緯度・経度情報もリストに追加
        trips_temp.append([
            row['rou_id'],
            row['junction_id_origin'],
            row['junction_id_destination'],
            int(str(row['トリップの起点時刻'])[8:10]) * 3600 + int(str(row['トリップの起点時刻'])[10:12]) * 60 + int(str(row['トリップの起点時刻'])[12:14]),
            row['自動車の用途'],
            row['緯度_destination'],
            row['経度_destination'],
            row['緯度_origin']
        ])
    # 出発時刻でソート
    trips_temp.sort(key=lambda x: x[3])

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# --- 5. trip / personTrip 出力 ---
for l in trips_temp:
    rou_id_str = f"t_{l[0]}"
    depart = str(l[3])
    from_junction = l[1]
    to_junction = l[2]  # デフォルトの目的地
    car_type = l[4]
    lat_dest = l[5]
    lon_dest = l[6]
    lat_origin = l[7]

    # --- ルールに応じてtripまたはpersonTripを生成 ---
    if car_type == 2:
        # トラック: 従来の<trip>
        trip = ET.Element('trip')
        trip.set('id', rou_id_str)
        trip.set('type', 'truck')
        trip.set('depart', depart)
        trip.set('fromJunction', from_junction)
        trip.set('toJunction', to_junction)
        rou_root.append(trip)
    else:
        # 普通車など: <person> + <personTrip>
        person = ET.Element('person')
        person.set('id', rou_id_str.replace('t_base_', 't_'))
        person.set('depart', depart)
        person.set('period', '1')

        person_trip = ET.SubElement(person, 'personTrip')
        person_trip.set('fromJunction', from_junction)
        person_trip.set('toJunction', to_junction)
        person_trip.set('modes', 'public car')

        rou_root.append(person)

# --- XML整形 & 書き出し ---
indent(rou_root)
rou_tree = ET.ElementTree(rou_root)
rou_tree.write(rou_file_path, encoding='utf-8', xml_declaration=True)

print(f"\n処理完了: {rou_file_path} を確認してください。")