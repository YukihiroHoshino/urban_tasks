import pandas
import xml.etree.ElementTree as ET
import numpy as np

#rou_file_path = 'rou_default_atarasii.rou.xml'
rou_file_path = '250724/exapmle2.rou.xml'

edg_xml = ET.parse('250724/brt_before.edg.xml').getroot()

edg_list = []

for child in edg_xml:
    if child.tag == 'edge':
        edg_list.append(child.attrib['id'])

rou_root = ET.Element('routes')

trips_temp = []

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
    for j in range(int(single_demand[2] * 1.5)):
            # 0~60の乱数を生成
            o = single_demand[0]
            d = single_demand[1]
            if o == "Anywhere":
                o = edg_list[np.random.randint(0, len(edg_list))]
            d = single_demand[1]
            if d == "Anywhere":
                d = edg_list[np.random.randint(0, len(edg_list))]
            trips_temp.append([f"t_add_{i}_{j}", o, d, 1])


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