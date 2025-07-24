import pandas
import xml.etree.ElementTree as ET
import numpy as np

df = pandas.read_csv('rou_9days_0106.rou.csv')

rou_file_path = 'rou_9days_add_16000.rou.xml'


rou_root = ET.Element('routes')

tree = ET.parse('outee.xml')

anywhere_origin = {}
anywhere_dest = {}

for x in ['E34', '1231325635#1', '314943854#10', '314943854#4', '128186295#4', '732836013#5']:
    anywhere_origin[x] = []
    anywhere_dest[x] = []

root = tree.getroot()

for child in root:
    if child.tag == 'vehicle':
        route = child.find('route')
        edges = route.get('edges').split(' ')
        if edges[0] in ['E34', '1231325635#1', '314943854#10', '314943854#4', '128186295#4', '732836013#5']:
            anywhere_origin[edges[0]].append(edges[-1])
        if edges[-1] in ['E34', '1231325635#1', '314943854#10', '314943854#4', '128186295#4', '732836013#5']:
            anywhere_dest[edges[-1]].append(edges[0])
        
trips_temp = []
for i in range(len(df)):
    id_ = df['rou_id'].iloc[i]
    from_ = df['edge_id_origin'].iloc[i]
    to_ = df['edge_id_destination'].iloc[i]
    depart_at_raw_ = str(df['トリップの起点時刻'].values[i])
    depart_at_ = int(depart_at_raw_[8:10])*3600 + int(depart_at_raw_[10:12])*60 + int(depart_at_raw_[12:14])
    if  16200 <= depart_at_ < 77400:
        trips_temp.append([id_,from_, to_, depart_at_])
        
add_rou_list = [["E34", "Anywhere", 6000],
                ["Anywhere", "E34",  6000],
                ["1231325635#1", "Anywhere", 360],
                ["Anywhere", "1231325635#1", 360],
                ["314943854#10", "Anywhere", 520],
                ["Anywhere", "314943854#10", 520],
                ["314943854#4", "Anywhere", 320],
                ["Anywhere", "314943854#4", 320],
                ["128186295#4", "Anywhere", 240],
                ["Anywhere", "128186295#4", 240],
                ["732836013#5", "Anywhere", 560],
                ["Anywhere", "732836013#5", 560],]

for i, single_demand in enumerate(add_rou_list):
    for k in range(single_demand[2]):
            # 0~60の乱数を生成
            o = single_demand[0]
            d = single_demand[1]
            if o == "Anywhere":
                o = anywhere_dest[d][k]
            if d == "Anywhere":
                d = anywhere_origin[o][k]
            rand = np.random.randint(18001, 21*3600)
            trips_temp.append([f"add_{i}_{k}", o, d, rand])


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

for i, single_demand in enumerate(trips_temp):
    trip = ET.SubElement(rou_root, 'trip')
    trip.set('id', f't_{single_demand[0]}')
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