# create_scenario_routes.py (修正版)
import pandas
import xml.etree.ElementTree as ET
import numpy as np
from collections import defaultdict
import copy

# --- ★★★ 設定項目 ★★★ ---
# 生成したいシナリオの番号を1から7の間で指定してください
SCENARIO_ID = 2
# --------------------------

# --- 入力ファイル ---
BASE_CSV_PATH = '250724/data/sunday_matched.csv'
BASE_OUT_NODES_PATH = '250724/data/sunday_out_nodes.xml'
# duarouterで検証済みの経路プールファイルを指定
VALIDATED_POOL_PATH = '250724/data/example_additional_out_nodes.xml' # 事前に生成したプールを指定

# --- 出力ファイル ---
FINAL_ROU_FILE_PATH = f'250724/data/sunday_added_v2_scenario_{SCENARIO_ID}.rou.xml'

# --- 固定パラメータ ---
ADAPT_RATE_TRUCK = 0.85
ADAPT_RATE_NORMAL = 0.30
# 乱数シードを固定して、毎回同じサンプリング結果を得る
np.random.seed(0)

# --- シナリオごとの追加トリップ定義 ---
# (リスト定義は長いので省略)
add_rou_list_1 = [ ["128185343", "Anywhere", 90], ["1231325634#1", "Anywhere", 90], ["Anywhere", "128185343", 90], ["Anywhere", "1231325634#1", 90], ["314943854#8", "Anywhere", 260], ["Anywhere", "314943854#8", 260], ["-314943854#4", "Anywhere", 80], ["314943854#4.70", "Anywhere", 80], ["Anywhere", "-314943854#4", 80], ["Anywhere", "314943854#4.70", 80], ["628774981#1", "Anywhere", 120], ["Anywhere", "628774981#1", 120], ["-732836013#5", "Anywhere", 280], ["Anywhere", "-732836013#5", 280] ]
add_rou_list_2_1_1 = [ ["128185343", "Anywhere", 1500], ["1231325634#1", "Anywhere", 1500], ["Anywhere", "128185343", 1500], ["Anywhere", "1231325634#1", 1500] ]
add_rou_list_2_1_2 = [ ["128185343", "Anywhere", 3000], ["1231325634#1", "Anywhere", 3000], ["Anywhere", "128185343", 3000], ["Anywhere", "1231325634#1", 3000] ]
add_rou_list_2_2_1 = [ ["E12.164", "Anywhere", 1500], ["1231325634#3", "Anywhere", 1500], ["Anywhere", "E12.164", 1500], ["Anywhere", "1231325634#3", 1500] ]
add_rou_list_2_2_2 = [ ["E12.164", "Anywhere", 3000], ["1231325634#3", "Anywhere", 3000], ["Anywhere", "E12.164", 3000], ["Anywhere", "1231325634#3", 3000] ]
add_rou_list_2_3_1 = [ ["-314943854#4", "Anywhere", 1500], ["314943854#4.70", "Anywhere", 1500], ["Anywhere", "-314943854#4", 1500], ["Anywhere", "314943854#4.70", 1500] ]
add_rou_list_2_3_2 = [ ["-314943854#4", "Anywhere", 3000], ["314943854#4.70", "Anywhere", 3000], ["Anywhere", "-314943854#4", 3000], ["Anywhere", "314943854#4.70", 3000] ]

scenario_map = {
    1: {"truck": add_rou_list_1},
    2: {"truck": add_rou_list_1, "normal": add_rou_list_2_1_1},
    3: {"truck": add_rou_list_1, "normal": add_rou_list_2_1_2},
    4: {"truck": add_rou_list_1, "normal": add_rou_list_2_2_1},
    5: {"truck": add_rou_list_1, "normal": add_rou_list_2_2_2},
    6: {"truck": add_rou_list_1, "normal": add_rou_list_2_3_1},
    7: {"truck": add_rou_list_1, "normal": add_rou_list_2_3_2},
}

def indent(elem, level=0):
    i = '\n' + level*'  '
    if len(elem):
        if not elem.text or not elem.text.strip(): elem.text = i + '  '
        if not elem.tail or not elem.tail.strip(): elem.tail = i
        for el in elem: indent(el, level+1)
        if not elem.tail or not elem.tail.strip(): elem.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

# --- 1. 検証済み経路プールを読み込み、ODペアごとに分類 ---
print(f"--- シナリオ {SCENARIO_ID} のルートファイルを生成します ---")
print(f"検証済み経路プール '{VALIDATED_POOL_PATH}' を読み込んでいます...")
validated_pool = defaultdict(list)
try:
    pool_tree = ET.parse(VALIDATED_POOL_PATH)
    for vehicle in pool_tree.getroot().findall('vehicle'):
        route = vehicle.find('route')
        if route is not None and 'edges' in route.attrib:
            edges = route.get('edges').split()
            if len(edges) > 1:
                od_pair = (edges[0], edges[-1])
                validated_pool[od_pair].append(route) # <route>要素を保存
    print(f"経路プールから {len(validated_pool)} 種類のODペア、合計 {sum(len(v) for v in validated_pool.values())} 件の有効な経路を読み込みました。")
except FileNotFoundError:
    print(f"エラー: 検証済み経路プールファイル '{VALIDATED_POOL_PATH}' が見つかりません。")
    print("事前に generate_trip_pool.py と duarouter を実行してください。")
    exit()

# --- 2. シナリオに基づき、プールから<trip>要素を生成 ---
final_added_trips = []
total_added_count = 0
selected_scenario = scenario_map.get(SCENARIO_ID)

if selected_scenario:
    for v_type, demand_list in selected_scenario.items():
        v_type_name = "truck" if v_type == "truck" else None
        depart_min, depart_max = (0, 86400) if v_type == "truck" else (32400, 61200) # Normal: 9-17時
        
        for i, (o_base, d_base, count) in enumerate(demand_list):
            candidate_routes = []
            if o_base != "Anywhere" and d_base != "Anywhere": # ODが両方固定
                candidate_routes.extend(validated_pool.get((o_base, d_base), []))
            elif o_base != "Anywhere": # 出発地のみ固定
                for (o, d), routes in validated_pool.items():
                    if o == o_base: candidate_routes.extend(routes)
            elif d_base != "Anywhere": # 目的地のみ固定
                for (o, d), routes in validated_pool.items():
                    if d == d_base: candidate_routes.extend(routes)
            
            if not candidate_routes:
                print(f"警告: {o_base} -> {d_base} に合致する有効な経路がプールに存在しません。スキップします。")
                continue
            
            sampled_indices = np.random.choice(len(candidate_routes), count, replace=True)
            
            for k, index in enumerate(sampled_indices):
                # 選択した<route>要素からfrom/toを特定
                route_element = candidate_routes[index]
                edges = route_element.get('edges').split()
                from_edge = edges[0]
                to_edge = edges[-1]

                # 新しい<trip>要素を生成
                new_trip = ET.Element('trip')
                new_trip.set('id', f't_add_{v_type}_{i}_{k}')
                new_trip.set('depart', str(np.random.randint(depart_min, depart_max)))
                if v_type_name:
                    new_trip.set('type', v_type_name)
                
                # from/to属性を設定
                if from_edge.endswith('N'): 
                    new_trip.set('fromJunction', from_edge[:-1])
                else: 
                    new_trip.set('from', from_edge)
                if to_edge.endswith('N'): 
                    new_trip.set('toJunction', to_edge[:-1])
                else: 
                    new_trip.set('to', to_edge)
                
                final_added_trips.append(new_trip)
            
            total_added_count += len(sampled_indices)

print(f"シナリオ {SCENARIO_ID} のために、{total_added_count} 台の追加トリップを生成しました。")


# --- 3. 元のトリップデータを読み込み、サンプリング ---
base_trips_to_add = []
try:
    print("元の交通データを読み込んでいます...")
    df = pandas.read_csv(BASE_CSV_PATH)
    tree_base = ET.parse(BASE_OUT_NODES_PATH)
    
    root_base = tree_base.getroot()
    dua = {child.attrib['id']: child.find('route').get('routeLength') 
           for child in root_base 
           if child.tag == 'vehicle' and child.find('route') is not None and 'routeLength' in child.find('route').attrib}

    df['route_length'] = [float(dua.get("t_" + str(rou_id), -1)) for rou_id in df["rou_id"]]
    df_long = df[df['route_length'] > 500].copy()
    
    num_days = df_long['運行日'].nunique()
    df_mini = pandas.DataFrame()
    
    if num_days > 0:
        df_trucks = df_long[df_long['自動車の用途'] == 2]
        df_normal = df_long[df_long['自動車の用途'] != 2]
        
        num_truck_per_day = int(len(df_trucks) / num_days / ADAPT_RATE_TRUCK)
        num_normal_per_day = int(len(df_normal) / num_days / ADAPT_RATE_NORMAL)

        print(f"運行日数: {num_days}日")
        print(f"1日あたりの目標トリップ数 (トラック: {num_truck_per_day}, 普通車: {num_normal_per_day})")

        def sample_by_vehicle_id(df_source, target_count):
            if df_source.empty or target_count == 0: return pandas.DataFrame()
            vehicle_ids = df_source['運行ID1'].unique()
            np.random.shuffle(vehicle_ids)
            trips_list = []
            count = 0
            for v_id in vehicle_ids:
                v_trips = df_source[df_source['運行ID1'] == v_id]
                trips_list.append(v_trips)
                count += len(v_trips)
                if count >= target_count: break
            return pandas.concat(trips_list, ignore_index=True) if trips_list else pandas.DataFrame()

        df_sampled_trucks = sample_by_vehicle_id(df_trucks, num_truck_per_day)
        df_sampled_normal = sample_by_vehicle_id(df_normal, num_normal_per_day)
        df_mini = pandas.concat([df_sampled_trucks, df_sampled_normal], ignore_index=True)
        
        print(f"元の交通データから {len(df_mini)} 台をサンプリングしました (トラック: {len(df_sampled_trucks)}, 普通車: {len(df_sampled_normal)})")
    else:
        print("元の交通データからサンプリングするデータがありませんでした。")

    for _, row in df_mini.iterrows():
        depart_raw = str(row['トリップの起点時刻'])
        depart = int(depart_raw[8:10])*3600 + int(depart_raw[10:12])*60 + int(depart_raw[12:14])
        
        trip = ET.Element('trip')
        trip.set('id', f't_base_{row["rou_id"]}')
        if row['自動車の用途'] == 2:
            trip.set('type', 'truck')
        trip.set('depart', str(depart))
        
        from_edge, to_edge = row['edge_id_origin'], row['edge_id_destination']
        if from_edge.endswith('N'): trip.set('fromJunction', from_edge[:-1])
        else: trip.set('from', from_edge)
        if to_edge.endswith('N'): trip.set('toJunction', to_edge[:-1])
        else: trip.set('to', to_edge)
        base_trips_to_add.append(trip)
except FileNotFoundError as e:
    print(f"警告: 元の交通データが見つかりません ({e.filename})。追加トリップのみでファイルを生成します。")


# --- 4. 全てのトリップを結合し、最終ファイルを出力 ---
rou_root = ET.Element('routes')

# 元のトリップと追加トリップを結合
all_elements = base_trips_to_add + final_added_trips

# 出発時刻でソート
all_elements.sort(key=lambda x: int(x.get('depart')))

# ソート済みの要素をrou_rootに追加
for elem in all_elements:
    rou_root.append(elem)

rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(FINAL_ROU_FILE_PATH, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n処理が完了しました。ファイル '{FINAL_ROU_FILE_PATH}' を確認してください。")