import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np

# --- ★★★ 設定項目 ★★★ ---

# --- 入力ファイル ---
# 1. ベースとなる交通流のルートファイル
BASE_ROU_FILE = '250724/data/thursday_BRT_dropped.rou.xml'

# 2. サンプリング対象となる、Junction指定のトリップ定義プール
ADDITIONAL_TRIP_POOL_FILE = '250724/data/oyakai_additional_trips_pool.rou.xml'

# 3. duarouterで経路計算が成功したトリップのIDリストを取得するためのファイル
VALIDATED_OUTPUT_FILE = '250724/data/oyakai_additional_out_nodes.xml'

# 4. ジャンクションの座標情報を取得するためのエッジファイル
JUNCTION_SOURCE_EDGE_FILE = '250724/data/edge_BRT.edg.xml'

# --- 出力ファイル ---
FINAL_ROU_FILE_PATH = '250724/data/thursday_BRT_oyakai_added.rou.xml'

# --- サンプリング定義 (Junction ID基準) ---
TRIP_LIST = [
    ("309574569", 5000, 'to'),
    ("309574569", 5000, 'from'),
    ("3909015091", 10000, 'to'),
    ("3909015091", 10000, 'from'),
    ("6313710997", 835, 'to'),
    ("6313710997", 835, 'from'),
    ("J287", 1250, 'to'),
    ("J287", 1250, 'from'),
]

np.random.seed(0) # 乱数のシードを固定

def indent(elem, level=0):
    """XML要素をきれいにインデントするためのヘルパー関数"""
    i = '\n' + level*'  '
    if len(elem):
        if not elem.text or not elem.text.strip(): elem.text = i + '  '
        if not elem.tail or not elem.tail.strip(): elem.tail = i
        for el in elem: indent(el, level+1)
        if not elem.tail or not elem.tail.strip(): elem.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

def get_traffic_elements_from_file(file_path):
    """XMLファイルから交通流要素のリストを取得"""
    elements = []
    try:
        tree = ET.parse(file_path)
        for elem in tree.getroot():
            if elem.tag in ['trip', 'person', 'vehicle', 'flow']:
                elements.append(elem)
        print(f"'{file_path}' から {len(elements)} 件の交通要素を読み込みました。")
    except (FileNotFoundError, ET.ParseError) as e:
        print(f"エラー: '{file_path}' の読み込みに失敗しました: {e}")
    return elements

def parse_junction_coordinates_from_edges(file_path):
    """
    .edg.xmlファイルを解析し、ジャンクションIDと座標の辞書を作成する。
    エッジの始点/終点座標を、対応するジャンクションの座標とみなす。
    """
    junction_coords = {}
    try:
        tree = ET.parse(file_path)
        for edge in tree.getroot().findall('edge'):
            shape = edge.get('shape')
            from_junc = edge.get('from')
            to_junc = edge.get('to')
            if shape and from_junc and to_junc:
                coords = shape.split(' ')
                # 始点座標
                if from_junc not in junction_coords:
                    lon, lat = map(float, coords[0].split(','))
                    junction_coords[from_junc] = {'lat': lat, 'lon': lon}
                # 終点座標
                if to_junc not in junction_coords:
                    lon, lat = map(float, coords[-1].split(','))
                    junction_coords[to_junc] = {'lat': lat, 'lon': lon}
        print(f"'{file_path}' から {len(junction_coords)} 件のユニークなジャンクション座標を生成しました。")
    except (FileNotFoundError, ET.ParseError, ValueError) as e:
        print(f"エラー: '{file_path}' の座標解析に失敗しました: {e}")
    return junction_coords

# --- 1. 座標情報と有効なトリップIDを読み込み ---
print("--- シナリオ生成を開始します ---")
junction_coords_map = parse_junction_coordinates_from_edges(JUNCTION_SOURCE_EDGE_FILE)
valid_trip_ids = set()
try:
    validated_tree = ET.parse(VALIDATED_OUTPUT_FILE)
    for vehicle in validated_tree.getroot().findall('vehicle'):
        valid_trip_ids.add(vehicle.get('id'))
    print(f"'{VALIDATED_OUTPUT_FILE}' から {len(valid_trip_ids)} 件の有効なトリップIDを読み込みました。")
except (FileNotFoundError, ET.ParseError) as e:
    print(f"エラー: '{VALIDATED_OUTPUT_FILE}' の読み込みに失敗しました: {e}")
    exit()

# --- 2. トリッププールから、有効なトリップのみを読み込み ---
trip_pool_data = []
try:
    pool_tree = ET.parse(ADDITIONAL_TRIP_POOL_FILE)
    for trip in pool_tree.getroot().findall('trip'):
        if trip.get('id') in valid_trip_ids:
            trip_pool_data.append({
                "fromJunction": trip.get('fromJunction'),
                "toJunction": trip.get('toJunction')
            })
    print(f"トリッププールから {len(trip_pool_data)} 件のサンプリング候補を読み込みました。")
except (FileNotFoundError, ET.ParseError) as e:
    print(f"エラー: '{ADDITIONAL_TRIP_POOL_FILE}' の読み込みに失敗しました: {e}")
    exit()

# --- 3. Junction ID に基づきランダムサンプリング ---
df_pool = pd.DataFrame(trip_pool_data)
sampled_trips_list = []

for i, (junction, count, direction) in enumerate(TRIP_LIST):
    candidates = df_pool[df_pool['toJunction' if direction == 'to' else 'fromJunction'] == junction]
    
    if len(candidates) > 0:
        sampled_df = candidates.sample(n=count, replace=True, random_state=0)
        rule_info = f"{i}_{direction}_{junction}"
        sampled_df['rule_info'] = rule_info
        sampled_trips_list.append(sampled_df)
    else:
        print(f"警告: {direction} '{junction}' に合致する候補がプールにありません。")

if sampled_trips_list:
    final_sampled_df = pd.concat(sampled_trips_list)
    final_sampled_df.reset_index(drop=True, inplace=True)
    print(f"合計 {len(final_sampled_df)} 件のトリップをサンプリングしました。")
else:
    final_sampled_df = pd.DataFrame()

# --- 4. ★★★ 目的地集約処理 ★★★ ---
if not final_sampled_df.empty:
    print("目的地の集約処理を適用しています...")
    df_coords = pd.DataFrame.from_dict(junction_coords_map, orient='index')

    # 出発地と目的地の座標を結合
    final_sampled_df = final_sampled_df.merge(df_coords, left_on='fromJunction', right_index=True, how='left').rename(columns={'lat': 'lat_origin', 'lon': 'lon_origin'})
    final_sampled_df = final_sampled_df.merge(df_coords, left_on='toJunction', right_index=True, how='left').rename(columns={'lat': 'lat_dest', 'lon': 'lon_dest'})
    final_sampled_df.fillna(0, inplace=True) # 座標が見つからない場合は0で埋める

# --- 5. personTrip形式のXML要素に変換 & 出発時刻をランダム化 ---
additional_elements = []
if not final_sampled_df.empty:
    print("追加トリップをpersonTrip形式に変換し、出発時刻をランダム化しています...")
    for index, row in final_sampled_df.iterrows():
        person = ET.Element('person')
        person.set('id', f"add_person_{row['rule_info']}_{index}")
        person.set('depart', str(np.random.randint(0, 86400)))
        person_trip = ET.SubElement(person, 'personTrip')
        person_trip.set('fromJunction', row['fromJunction'])
        person_trip.set('toJunction', row['toJunction']) # 集約済みの可能性あり
        person_trip.set('modes', 'public car')
        additional_elements.append(person)

# --- 6. ベース交通流を読み込み ---
base_elements = get_traffic_elements_from_file(BASE_ROU_FILE)

# --- 7. 全ての交通流を結合して出力 ---
print("最終的なルートファイルを生成しています...")
rou_root = ET.Element('routes')
vtype_truck = ET.SubElement(rou_root, 'vType'); vtype_truck.set('id', 'truck'); vtype_truck.set('vClass', 'truck')
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

all_elements = base_elements + additional_elements
sortable = [el for el in all_elements if 'depart' in el.attrib]
non_sortable = [el for el in all_elements if 'depart' not in el.attrib]
sortable.sort(key=lambda x: float(x.get('depart')))
for elem in non_sortable: rou_root.append(elem)
for elem in sortable: rou_root.append(elem)
rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(FINAL_ROU_FILE_PATH, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n処理が完了しました。ファイル '{FINAL_ROU_FILE_PATH}' を確認してください。")