import pandas
import xml.etree.ElementTree as ET
import numpy as np

# 乱数シードを固定し、毎回同じ結果を生成
np.random.seed(0) 

# --- 入力ファイル ---
df = pandas.read_csv('250724/data/example_matched.csv')
tree = ET.parse('250724/data/example_out_nodes.xml')

# --- 出力ファイル ---
rou_file_path = '250724/data/example_dropped_v2.rou.xml'

# ETC2.0の普及率を書き換え
ADAPT_RATE_TRUCK = 0.56
ADAPT_RATE_NORMAL = 0.25

# --- 1. 経路学習用の情報を読み込み ---
root = tree.getroot()
dua = {}

for child in root:
    if child.tag == 'vehicle':
        id_val = child.attrib['id']
        route = child.find('route')
        if route is not None and 'routeLength' in route.attrib:
            route_length = route.get('routeLength')
            dua[id_val] = route_length

route_length_list = []
for i in range(len(df)):
    id_val = "t_" + df["rou_id"].iloc[i]
    if id_val in dua:
        route_length_list.append(float(dua[id_val]))
    else:
        route_length_list.append(-1)

df['route_length'] = route_length_list

# --- 2. 短すぎるトリップを除外 ---
df_long = df[df['route_length'] > 500].copy()

# --- 3. 現実の交通量に基づいたサンプリング処理 ---

# 異なる運行日の日数を計算
num_days = df_long['運行日'].nunique()

if num_days == 0:
    print("有効なデータが存在しないため、処理を中断します。")
    df_mini = pandas.DataFrame() # 空のデータフレームを作成
else:
    # truckとそれ以外の車両にデータを分割
    df_trucks = df_long[df_long['自動車の種別'] == 1]
    df_normal = df_long[df_long['自動車の種別'] != 1]

    # 1日あたりの平均交通量を算出
    num_truck_per_day = int(len(df_trucks) / num_days / ADAPT_RATE_TRUCK) if num_days > 0 else 0
    num_normal_per_day = int(len(df_normal) / num_days / ADAPT_RATE_NORMAL) if num_days > 0 else 0

    print(f"運行日数: {num_days}日")
    print(f"1日あたりのトラックの目標トリップ数: {num_truck_per_day}")
    print(f"1日あたりの普通車の目標トリップ数: {num_normal_per_day}")

    # 運行ID1を単位としてランダムにサンプリングする関数
    def sample_by_vehicle_id(df_source, target_trip_count):
        if df_source.empty or target_trip_count == 0:
            return pandas.DataFrame()

        # 車両IDのリストをシャッフル
        vehicle_ids = df_source['運行ID1'].unique()
        np.random.shuffle(vehicle_ids)
        
        selected_trips_list = []
        current_trip_count = 0
        
        # 目標数に達するまで車両を追加
        for v_id in vehicle_ids:
            vehicle_trips = df_source[df_source['運行ID1'] == v_id]
            selected_trips_list.append(vehicle_trips)
            current_trip_count += len(vehicle_trips)
            if current_trip_count >= target_trip_count:
                break
                
        return pandas.concat(selected_trips_list, ignore_index=True)

    # truckとnormalそれぞれでサンプリングを実行
    df_sampled_trucks = sample_by_vehicle_id(df_trucks, num_truck_per_day)
    df_sampled_normal = sample_by_vehicle_id(df_normal, num_normal_per_day)

    # 最終的なサンプリング結果を結合
    df_mini = pandas.concat([df_sampled_trucks, df_sampled_normal], ignore_index=True)

    print(f"抽出された合計トリップ数: {len(df_mini)} (トラック: {len(df_sampled_trucks)}, 普通車: {len(df_sampled_normal)})")


# --- 4. rou.xmlファイルへの書き出し準備 ---
rou_root = ET.Element('routes')

trips_temp = []
for i in range(len(df_mini)):
    row = df_mini.iloc[i]
    id_ = row['rou_id']
    from_ = row['edge_id_origin']
    to_ = row['edge_id_destination']
    car_type_ = row['自動車の種別']
    depart_at_raw_ = str(row['トリップの起点時刻'])
    depart_at_ = int(depart_at_raw_[8:10])*3600 + int(depart_at_raw_[10:12])*60 + int(depart_at_raw_[12:14])
    trips_temp.append([id_, from_, to_, depart_at_, car_type_])

trips_temp.sort(key=lambda x: x[3])
for l in trips_temp:
    l[3] = str(int(l[3]))

def indent(elem, level=0):
    i = '\n' + level*'  '
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + '  '
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# --- 5. 最終的なrou.xmlを出力 ---
for i, single_demand in enumerate(trips_temp):
    trip = ET.SubElement(rou_root, 'trip')
    trip.set('id', f't_{single_demand[0]}')
    
    car_type = single_demand[4]
    if car_type == 1:
        trip.set('type', 'truck')

    trip.set('depart', str(single_demand[3]))
        
    from_edge = single_demand[1]
    to_edge = single_demand[2]
    
    if from_edge.endswith('N'):
        trip.set('fromJunction', from_edge[:-1])
    else:
        trip.set('from', from_edge)
    if to_edge.endswith('N'):
        trip.set('toJunction', to_edge[:-1])
    else:
        trip.set('to', to_edge)

rou_tree = ET.ElementTree(rou_root)

with open(rou_file_path, 'w', encoding='utf-8') as file:
    indent(rou_root)
    rou_tree.write(file, encoding='unicode', xml_declaration=True)

print(f"\n処理が完了しました。ファイル '{rou_file_path}' を確認してください。")