import pandas
import xml.etree.ElementTree as ET
import numpy as np

# 乱数シードを固定し、毎回同じ結果を生成
np.random.seed(0) 

# --- 入力ファイル ---
# 元のトリップデータ
df = pandas.read_csv('250724/data/example_matched.csv')

# 元のトリップの経路長データ
tree_main_trips = ET.parse('250724/data/example_out_nodes.xml')

# 追加トリップの経路学習用データ
tree_additional_trips = ET.parse('250724/data/example_additional_out_nodes.xml')

# --- 出力ファイル ---
rou_file_path = '250724/data/example_added_v2.rou.xml'


# --- 1. 追加トリップの有効なODペアを学習 ---
anywhere_origin = {}
anywhere_dest = {}
key_edges = ['E34', '1231325635#1', '314943854#10', '314943854#4', '128186295#4', '732836013#5']

for x in key_edges:
    anywhere_origin[x] = []
    anywhere_dest[x] = []

root_additional = tree_additional_trips.getroot()

for child in root_additional:
    if child.tag == 'vehicle':
        route = child.find('route')
        if route is not None and 'edges' in route.attrib:
            edges = route.get('edges').split(' ')
            if edges: # ルートが空でないことを確認
                start_edge = edges[0]
                end_edge = edges[-1]
                if start_edge in key_edges:
                    anywhere_origin[start_edge].append(end_edge)
                if end_edge in key_edges:
                    anywhere_dest[end_edge].append(start_edge)

# --- 2. 元のトリップの経路長を読み込み、フィルタリング ---
root_main = tree_main_trips.getroot()
dua = {}

for child in root_main:
    if child.tag == 'vehicle':
        id_val = child.attrib['id']
        route = child.find('route')
        if route is not None and 'routeLength' in route.attrib:
            route_length_val = route.get('routeLength')
            dua[id_val] = route_length_val

route_length_list = []
for i in range(len(df)):
    id_val = "t_" + df["rou_id"].iloc[i]
    if id_val in dua:
        route_length_list.append(float(dua[id_val]))
    else:
        route_length_list.append(-1)

df['route_length'] = route_length_list
df_long = df[df['route_length'] > 500].copy()

# --- 3. 現実の交通量に基づいたサンプリング処理 ---

# 異なる運行日の日数を計算
num_days = df_long['運行日'].nunique()

if num_days == 0:
    print("有効なデータが存在しないため、処理を中断します。")
    exit()

# truckとそれ以外の車両にデータを分割
df_trucks = df_long[df_long['自動車の種別'] == 1]
df_normal = df_long[df_long['自動車の種別'] != 1]

# 1日あたりの平均交通量を算出
num_truck_per_day = int(len(df_trucks) / num_days) if num_days > 0 else 0
num_normal_per_day = int(len(df_normal) / num_days) if num_days > 0 else 0

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

# --- 4. 元のトリップと追加トリップを結合 ---
trips_temp = []

# サンプリングされた元のトリップを追加
for i in range(len(df_mini)):
    row = df_mini.iloc[i]
    id_ = row['rou_id']
    from_ = row['edge_id_origin']
    to_ = row['edge_id_destination']
    car_type_ = row['自動車の種別']
    depart_at_raw_ = str(row['トリップの起点時刻'])
    depart_at_ = int(depart_at_raw_[8:10])*3600 + int(depart_at_raw_[10:12])*60 + int(depart_at_raw_[12:14])
    if 16200 <= depart_at_ < 77400:
        trips_temp.append([id_, from_, to_, depart_at_, car_type_])

# 追加トリップの定義
add_rou_list = [["E34", "Anywhere", 6000], ["Anywhere", "E34",  6000],
                ["1231325635#1", "Anywhere", 360], ["Anywhere", "1231325635#1", 360],
                ["314943854#10", "Anywhere", 520], ["Anywhere", "314943854#10", 520],
                ["314943854#4", "Anywhere", 320], ["Anywhere", "314943854#4", 320],
                ["128186295#4", "Anywhere", 240], ["Anywhere", "128186295#4", 240],
                ["732836013#5", "Anywhere", 560], ["Anywhere", "732836013#5", 560]]

# 追加トリップと結合
for i, single_demand in enumerate(add_rou_list):
    o_base = single_demand[0]
    d_base = single_demand[1]
    
    # 追加可能なペア数を事前に確認
    if o_base == "Anywhere":
        valid_pairs = anywhere_dest.get(d_base)
        if not valid_pairs: continue
        num_available = len(valid_pairs)
    else: # d_base == "Anywhere"
        valid_pairs = anywhere_origin.get(o_base)
        if not valid_pairs: continue
        num_available = len(valid_pairs)
        
    num_to_add = min(single_demand[2], num_available)

    for k in range(num_to_add):
        o = o_base
        d = d_base
        if o == "Anywhere":
            o = valid_pairs[k]
        if d == "Anywhere":
            d = valid_pairs[k]
        rand = np.random.randint(18001, 21*3600)
        trips_temp.append([f"add_{i}_{k}", o, d, rand, 0]) # 追加トリップの種別は全て0とする

# --- 5. 最終的なrou.xmlを出力 ---
trips_temp.sort(key=lambda x: x[3])
for l in trips_temp:
    l[3] = str(int(l[3]))

rou_root = ET.Element('routes')

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

for i, single_demand in enumerate(trips_temp):
    trip = ET.SubElement(rou_root, 'trip')
    trip.set('id', f't_{single_demand[0]}')
    
    car_type = single_demand[4]
    if car_type == 1:
        trip.set('type', 'truck')
        
    trip.set('depart', str(single_demand[3]))
    
    # from/to の設定
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