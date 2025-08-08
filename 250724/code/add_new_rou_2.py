import pandas
import xml.etree.ElementTree as ET
import numpy as np
np.random.seed(0) 

# --- 入力ファイル ---
# 元のトリップデータ
df = pandas.read_csv('250724/data/example_matched.csv')

# 元のトリップの経路長データ
tree_main_trips = ET.parse('250724/data/example_out_nodes.xml')

# 追加トリップの経路学習用データ
tree_additional_trips = ET.parse('250724/data/example_additional_out_nodes.xml')

# --- 出力ファイル ---
rou_file_path = '250724/data/example_added.rou.xml'


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

# --- 2. 元のトリップの経路長を読み込み、フィルタリングとサンプリングを行う ---
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
df_long = df[df['route_length'] > 500]

n_samples = min(30000, len(df_long))
if n_samples < 30000:
    print(f"警告: 500mを超えるトリップが {len(df_long)} 件しかなかったため、{n_samples} 件のみサンプリングします。")
df_mini = df_long.sample(n=n_samples, random_state=0)

# --- 4. 元のトリップと追加トリップを結合 ---
trips_temp = []

# サンプリングされた元のトリップを追加
for i in range(len(df_mini)):
    row = df_mini.iloc[i]
    id_ = row['rou_id']
    from_ = row['edge_id_origin']
    to_ = row['edge_id_destination']
    car_type_ = row['自動車の用途']
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
        if not anywhere_dest.get(d_base): continue # 有効なペアがなければスキップ
        num_available = len(anywhere_dest[d_base])
    else: # d_base == "Anywhere"
        if not anywhere_origin.get(o_base): continue # 有効なペアがなければスキップ
        num_available = len(anywhere_origin[o_base])
        
    num_to_add = min(single_demand[2], num_available)

    for k in range(num_to_add):
        o = o_base
        d = d_base
        if o == "Anywhere":
            o = anywhere_dest[d][k]
        if d == "Anywhere":
            d = anywhere_origin[o][k]
        rand = np.random.randint(18001, 21*3600)
        trips_temp.append([f"add_{i}_{k}", o, d, rand, 1]) # 追加トリップの用途は全て1とする

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
    if car_type == 2:
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