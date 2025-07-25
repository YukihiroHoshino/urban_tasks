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

df_mini = df_long.sample(n=1000000, random_state=0)
df_mini.to_csv('250724//data/example_matched.csv', index=False)

rou_root = ET.Element('routes')

trips_temp = []
for i in range(len(df_mini)):
    id_ = df_mini['rou_id'].iloc[i]
    from_ = df_mini['edge_id_origin'].iloc[i]
    to_ = df_mini['edge_id_destination'].iloc[i]
    depart_at_raw_ = str(df_mini['トリップの起点時刻'].values[i])
    depart_at_ = int(depart_at_raw_[8:10])*3600 + int(depart_at_raw_[10:12])*60 + int(depart_at_raw_[12:14])
    trips_temp.append([id_,from_, to_, depart_at_])
    #if from_ not in ['775774302#0', "675094548#0", '614360368#1', '-595128129#2', '81049778#2', '314943856#11-AddedOnRampEdge', '62120959#3', '62120959#1', 
    #     '1182813965#1', '42752018#2', '71763753#2', '-32133087#1', '775774302#0-AddedOffRampEdge', '-291905174#1', 
    #     '314943856#11', '67153325#2', '72183626', '76202644#8', '62120959#2', '62120959#4', '76202644#10', '849787175#35', 
    #     '763353054', '67151411', '763353053', '81049778#3', '76203255', '72183451', '62120958#1', '849961304#1', '-43992529']:
    #if from_ not in ['775774302#0', "675094548#0",'314943856#13', '614360368#1', '81050210#3', '203680876#2', '81049778#2', '1182813963', '-76202644#8', '373862787', '314943851#2', '71763753#2', '-732836013#1', '775774302#0-AddedOffRampEdge', '351777129#9', '80092519', '763353054', '314943856#13-AddedOnRampEdge', '81050164#1', '67153325#1-AddedOnRampEdge', '-1184585975#3', '62120958#1', '686626654#4', '72502348#3-AddedOffRampEdge', '-76202644#14', '62120959#3', '1182813965#1', '291905174#1', '-32133087#7', '-373862788#0', '-291905174#1', '849961304#0', '483075115#1', '374038306', '-595128127#1', '72183626', '76202644#8', '849787175#35', '128185344#2', '-314943854#0', '71763753#1', '763353053', '81049778#1', '849961304#1', '-78313088', '81049778#0', '672428421#4', '62120959#7', '314943856#11-AddedOnRampEdge', '62120959#1', '60057863#2', '849961299#1', '42752018#2', '-32133087#1', '76202644#12', '139996912#0', '447675894#3', '-614365450', '80092004', '62120959#2', '62120959#4', '76202644#10', '228025766', '-60057863#2', '-76202644#10', '351777129#8', '42751934#1', '81049778#3', '34122877#0', '-77075054#0', '-81050210#6', '42752020#0', '80091723', '-595128129#2', '351777129#7', '314943856#0', '71763753#0', '128185344#1', '-849787175#40', '-41249476#1', '-41249476#2', '314943856#11', '67153325#2', '62120959#0', '-732836013#0', '-373862797#2', '72502348#3', '67153325#3', '67151411', '76203255', '72183451', '455725528', '-43992529', '373864074#4']:
        #if np.random.rand() < 0.5:  
    #        trips_temp.append([id_ + "sub", from_, to_, depart_at_ + 10])

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