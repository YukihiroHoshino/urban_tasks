import pandas
import xml.etree.ElementTree as ET

#使用例
#df = pandas.read_csv('filename_matched.csv')
#tree = ET.parse('filename_out_nodes.xml')
#rou_file_path = './filename_dropped.rou.xml'

#使用例
df = pandas.read_csv('250724/data/example_matched.csv')
tree = ET.parse('250724/data/example_out_nodes.xml')
rou_file_path = '250724/data/example_dropped.rou.xml'


root = tree.getroot()

dua = {}

for child in root:
    if child.tag == 'vehicle':
        id = child.attrib['id']
        route = child.find('route')
        route_length = route.get('routeLength')
        dua[id] = route_length

route_length = []
for i in range(len(df)):
    id = "t_" + df["rou_id"][i]
    if id in dua:
        route_length.append(float(dua[id]))
    else:
        route_length.append(-1)

df['route_length'] = route_length

df_long = df[df['route_length'] > 500]

#df_mini = df_long.sample(n=1000000, random_state=0)
df_mini = df_long.sample(n=10000, random_state=0)
#df_mini.to_csv('250724//data/example_matched.csv', index=False)

rou_root = ET.Element('routes')

trips_temp = []
# ★★★ 変更点1: 「自動車の種別」もリストに追加 ★★★
for i in range(len(df_mini)):
    id_ = df_mini['rou_id'].iloc[i]
    from_ = df_mini['edge_id_origin'].iloc[i]
    to_ = df_mini['edge_id_destination'].iloc[i]
    car_type_ = df_mini['自動車の種別'].iloc[i] # 自動車の種別を取得
    depart_at_raw_ = str(df_mini['トリップの起点時刻'].values[i])
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

# ★★★ 変更点2: XML生成時に自動車の種別を判定 ★★★
for i, single_demand in enumerate(trips_temp):
    trip = ET.SubElement(rou_root, 'trip')
    trip.set('id', f't_{single_demand[0]}')
    
    # 自動車の種別（single_demand[4]）が1の場合、type="truck" を追加
    car_type = single_demand[4]
    if car_type == 1:
        trip.set('type', 'truck')

    trip.set('depart', str(single_demand[3]))
        
    if single_demand[1][-1] == 'N':
        trip.set('fromJunction', single_demand[1][:-1])
    else:
        trip.set('from', single_demand[1])
    if single_demand[2][-1] == 'N':
        trip.set('toJunction', single_demand[2][:-1])
    else:
        trip.set('to', single_demand[2])

rou_tree = ET.ElementTree(rou_root)

with open(rou_file_path, 'w', encoding='utf-8') as file:
    indent(rou_root)
    rou_tree.write(file, encoding='unicode', xml_declaration=True)