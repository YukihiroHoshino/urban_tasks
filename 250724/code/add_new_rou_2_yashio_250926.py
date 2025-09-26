# add_new_rou_2.py (再修正版)
import pandas
import xml.etree.ElementTree as ET
import numpy as np
from collections import defaultdict

# --- ★★★ 設定項目 ★★★ ---
SCENARIO_ID = 7
# --------------------------

# --- 入力ファイル ---
BASE_CSV_PATH = '250724/data/sunday_matched.csv'
BASE_OUT_NODES_PATH = '250724/data/sunday_out_nodes.xml'
VALIDATED_POOL_PATH = '250724/data/example_additional_out_nodes.xml'

# --- 出力ファイル ---
FINAL_ROU_FILE_PATH = f'250724/data/sunday_added_v2_scenario_{SCENARIO_ID}.rou.xml'

# --- 固定パラメータ ---
ADAPT_RATE_TRUCK = 0.85
ADAPT_RATE_NORMAL = 0.30
np.random.seed(0)

# --- 道の駅IDとエッジIDの対応 ---
# (このスクリプトでは直接使用しませんが、定義として残しておきます)
pa_to_edge_map = {
    "michinoeki_1_1": "128185343",
    "michinoeki_1_2": "1231325634#1",
    "michinoeki_2_1": "E12.164",
    "michinoeki_2_2": "1231325634#3",
    "michinoeki_3_1": "-314943854#4",
    "michinoeki_3_2": "314943854#4.70"
}

# --- シナリオごとの追加トリップ定義 ---
add_rou_list_1 = [ ["128185343", "Anywhere", 90], ["1231325634#1", "Anywhere", 90], ["Anywhere", "128185343", 90], ["Anywhere", "1231325634#1", 90], ["314943854#8", "Anywhere", 260], ["Anywhere", "314943854#8", 260], ["-314943854#4", "Anywhere", 80], ["314943854#4.70", "Anywhere", 80], ["Anywhere", "-314943854#4", 80], ["Anywhere", "314943854#4.70", 80], ["628774981#1", "Anywhere", 120], ["Anywhere", "628774981#1", 120], ["-732836013#5", "Anywhere", 280], ["Anywhere", "-732836013#5", 280] ]
add_rou_list_2_1_1 = [ ["michinoeki_1_1", 1500], ["michinoeki_1_2", 1500] ]
add_rou_list_2_1_2 = [ ["michinoeki_1_1", 3000], ["michinoeki_1_2", 3000] ]
add_rou_list_2_2_1 = [ ["michinoeki_2_1", 1500], ["michinoeki_2_2", 1500] ]
add_rou_list_2_2_2 = [ ["michinoeki_2_1", 3000], ["michinoeki_2_2", 3000] ]
add_rou_list_2_3_1 = [ ["michinoeki_3_1", 1500], ["michinoeki_3_2", 1500] ]
add_rou_list_2_3_2 = [ ["michinoeki_3_1", 3000], ["michinoeki_3_2", 3000] ]

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

# --- 1. 検証済み経路プールを読み込み、分類 ---
print(f"--- シナリオ {SCENARIO_ID} のルートファイルを生成します ---")
print(f"検証済み経路プール '{VALIDATED_POOL_PATH}' を読み込んでいます...")
# 産業施設用(L1)のODペアごとのプール
validated_od_pool = defaultdict(list)
# 道の駅用(L2)のparkingAreaごとのプール
validated_pa_pool = defaultdict(list)
known_pa_ids = pa_to_edge_map.keys()

try:
    pool_tree = ET.parse(VALIDATED_POOL_PATH)
    for vehicle in pool_tree.getroot().findall('vehicle'):
        route = vehicle.find('route')
        if route is None or 'edges' not in route.attrib:
            continue
        
        edges = route.get('edges').split()
        if len(edges) <= 1:
            continue
            
        vehicle_id = vehicle.get('id', '')
        
        # ★★★ ロジック変更点 ★★★
        # vehicle_idに道の駅IDが含まれるかチェック
        found_pa_id = None
        for pa_id in known_pa_ids:
            if pa_id in vehicle_id:
                found_pa_id = pa_id
                break
        
        if found_pa_id:
            # 道の駅トリップの経路としてプール
            validated_pa_pool[found_pa_id].append(route)
        else:
            # 産業施設トリップの経路としてプール
            od_pair = (edges[0], edges[-1])
            validated_od_pool[od_pair].append(route)

    print(f"経路プールから産業施設用のODペア {len(validated_od_pool)} 種類を読み込みました。")
    print(f"経路プールから道の駅用のparkingArea {len(validated_pa_pool)} 種類を読み込みました。")
except FileNotFoundError:
    print(f"エラー: 検証済み経路プールファイル '{VALIDATED_POOL_PATH}' が見つかりません。")
    exit()

# --- 2. シナリオに基づき、プールから<trip>要素を生成 ---
final_added_trips = []
total_added_count = 0
selected_scenario = scenario_map.get(SCENARIO_ID)

if selected_scenario:
    for v_type, demand_list in selected_scenario.items():
        v_type_name = "truck" if v_type == "truck" else 'car'
        depart_min, depart_max = (0, 86400) if v_type == "truck" else (32400, 61200)
        
        for i, demand_item in enumerate(demand_list):
            
            # --- 産業施設トリップ (従来通り validated_od_pool を使用) ---
            if len(demand_item) == 3:
                o_base, d_base, count = demand_item
                candidate_routes = []
                if o_base != "Anywhere" and d_base != "Anywhere":
                    candidate_routes.extend(validated_od_pool.get((o_base, d_base), []))
                elif o_base != "Anywhere":
                    for (o, d), routes in validated_od_pool.items():
                        if o == o_base: candidate_routes.extend(routes)
                elif d_base != "Anywhere":
                    for (o, d), routes in validated_od_pool.items():
                        if d == d_base: candidate_routes.extend(routes)
                
                if not candidate_routes:
                    print(f"警告: {o_base} -> {d_base} に合致する有効な経路がプールに存在しません。")
                    continue
                
                sampled_indices = np.random.choice(len(candidate_routes), count, replace=True)
                for k, index in enumerate(sampled_indices):
                    # ... (トリップ生成部分は変更なし) ...
                    route_element = candidate_routes[index]
                    edges = route_element.get('edges').split()
                    from_edge, to_edge = edges[0], edges[-1]
                    new_trip = ET.Element('trip')
                    new_trip.set('id', f't_add_{v_type}_{i}_{k}')
                    new_trip.set('depart', str(np.random.randint(depart_min, depart_max)))
                    if v_type == "truck": new_trip.set('type', v_type_name)
                    if from_edge.endswith('N'): new_trip.set('fromJunction', from_edge[:-1])
                    else: new_trip.set('from', from_edge)
                    if to_edge.endswith('N'): new_trip.set('toJunction', to_edge[:-1])
                    else: new_trip.set('to', to_edge)
                    final_added_trips.append(new_trip)
                total_added_count += len(sampled_indices)

            # ★★★ ロジック変更点 ★★★
            # --- 道の駅トリップ (新しい validated_pa_pool を使用) ---
            elif len(demand_item) == 2:
                pa_id, count = demand_item
                candidate_routes = validated_pa_pool.get(pa_id)
                
                if not candidate_routes:
                    print(f"警告: parkingArea '{pa_id}' に合致する有効な経路がプールに存在しません。")
                    continue

                sampled_indices = np.random.choice(len(candidate_routes), count, replace=True)
                for k, index in enumerate(sampled_indices):
                    route_element = candidate_routes[index]
                    edges = route_element.get('edges').split()
                    edge_od = edges[0] # 出発地と目的地は同じはず

                    new_trip = ET.Element('trip')
                    new_trip.set('id', f't_add_{v_type}_{i}_{k}')
                    new_trip.set('type', v_type_name)
                    new_trip.set('depart', str(np.random.randint(depart_min, depart_max)))
                    new_trip.set('from', edge_od)
                    new_trip.set('to', edge_od)
                    
                    stop = ET.SubElement(new_trip, 'stop')
                    stop.set('parkingArea', pa_id)
                    duration = str(np.random.randint(5400, 7201))
                    stop.set('duration', duration)
                    final_added_trips.append(new_trip)
                total_added_count += len(sampled_indices)

print(f"シナリオ {SCENARIO_ID} のために、{total_added_count} 台の追加トリップを生成しました。")

# --- 3. 元のトリップデータを読み込み、サンプリング ---
# (このセクションは変更ありません)
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
        for _, row in df_mini.iterrows():
            depart_raw = str(row['トリップの起点時刻'])
            depart = int(depart_raw[8:10])*3600 + int(depart_raw[10:12])*60 + int(depart_raw[12:14])
            trip = ET.Element('trip')
            trip.set('id', f't_base_{row["rou_id"]}')
            if row['自動車の用途'] == 2: trip.set('type', 'truck')
            trip.set('depart', str(depart))
            from_edge, to_edge = row['edge_id_origin'], row['edge_id_destination']
            if from_edge.endswith('N'): trip.set('fromJunction', from_edge[:-1])
            else: trip.set('from', from_edge)
            if to_edge.endswith('N'): trip.set('toJunction', to_edge[:-1])
            else: trip.set('to', to_edge)
            base_trips_to_add.append(trip)
except FileNotFoundError as e:
    print(f"警告: 元の交通データが見つかりません ({e.filename})。")

# --- 4. 全てのトリップを結合し、最終ファイルを出力 ---
# (このセクションは変更ありません)
rou_root = ET.Element('routes')
all_elements = base_trips_to_add + final_added_trips
all_elements.sort(key=lambda x: int(x.get('depart')))
for elem in all_elements:
    rou_root.append(elem)
rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(FINAL_ROU_FILE_PATH, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n処理が完了しました。ファイル '{FINAL_ROU_FILE_PATH}' を確認してください。")