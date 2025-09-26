# add_new_rou_1.py (再修正版)
import xml.etree.ElementTree as ET
import numpy as np

# --- 設定 ---
# duarouterで検証後、各ペアから十分にサンプリングできるだけの数を生成します
NUM_TRIPS_PER_PAIR = 3000
EDG_FILE_PATH = '250724/data/example.edg.xml'
OUTPUT_POOL_FILE = '250724/data/example_additional_trips_pool.rou.xml'

# --- 道の駅IDとエッジIDの対応 ---
# (このスクリプトでは直接使用しませんが、定義として残しておきます)
michinoeki_to_edge_map = {
    "michinoeki_1_1": "128185343",
    "michinoeki_1_2": "1231325634#1",
    "michinoeki_2_1": "E12.164",
    "michinoeki_2_2": "1231325634#3",
    "michinoeki_3_1": "-314943854#4",
    "michinoeki_3_2": "314943854#4.70"
}

# --- 全シナリオのトリップ定義をここに集約 ---
all_lists = {
    "L1": [ # 産業施設: 変更なし
        ["128185343", "Anywhere"], ["1231325634#1", "Anywhere"],
        ["Anywhere", "128185343"], ["Anywhere", "1231325634#1"],
        ["314943854#8", "Anywhere"], ["Anywhere", "314943854#8"],
        ["-314943854#4", "Anywhere"], ["314943854#4.70", "Anywhere"],
        ["Anywhere", "-314943854#4"], ["Anywhere", "314943854#4.70"],
        ["628774981#1", "Anywhere"], ["Anywhere", "628774981#1"],
        ["-732836013#5", "Anywhere"], ["Anywhere", "-732836013#5"]
    ],
    "L211": [["michinoeki_1_1"], ["michinoeki_1_2"]],
    "L212": [["michinoeki_1_1"], ["michinoeki_1_2"]],
    "L221": [["michinoeki_2_1"], ["michinoeki_2_2"]],
    "L222": [["michinoeki_2_1"], ["michinoeki_2_2"]],
    "L231": [["michinoeki_3_1"], ["michinoeki_3_2"]],
    "L232": [["michinoeki_3_1"], ["michinoeki_3_2"]]
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

# --- メイン処理 ---
try:
    edg_xml = ET.parse(EDG_FILE_PATH).getroot()
    edg_list = [child.attrib['id'] for child in edg_xml if child.tag == 'edge']
except FileNotFoundError:
    print(f"エラー: エッジファイルが見つかりません: {EDG_FILE_PATH}")
    exit()

rou_root = ET.Element('routes')
trip_counter = 0

print(f"各定義について {NUM_TRIPS_PER_PAIR} 台のトリップを生成します...")

for list_name, demand_list in all_lists.items():
    # --- L1: 産業施設トリップの生成 ---
    if list_name.startswith("L1"):
        for o_base, d_base in demand_list:
            for j in range(NUM_TRIPS_PER_PAIR):
                while True:
                    o, d = o_base, d_base
                    if o == "Anywhere": o = np.random.choice(edg_list)
                    if d == "Anywhere": d = np.random.choice(edg_list)
                    if o != d: break
                
                trip = ET.SubElement(rou_root, 'trip')
                trip.set('id', f'pool_L1_{trip_counter}')
                trip.set('depart', "0")
                trip.set('from', o)
                trip.set('to', d)
                trip_counter += 1

    # --- L2: 道の駅トリップの生成 ---
    elif list_name.startswith("L2"):
        for item in demand_list:
            pa_id = item[0]
            
            # --- <stop> 形式のトリップのみを生成 ---
            for j in range(NUM_TRIPS_PER_PAIR):
                edge_od = np.random.choice(edg_list)
                
                trip = ET.SubElement(rou_root, 'trip')
                # ★重要: IDにpa_idを含めることで、add_new_rou_2.pyがどの道の駅の経路か識別できるようにする
                trip.set('id', f'pool_{list_name}_{pa_id}_{trip_counter}')
                trip.set('type', 'car')
                trip.set('depart', '0')
                trip.set('from', edge_od)
                trip.set('to', edge_od)
                
                stop = ET.SubElement(trip, 'stop')
                stop.set('parkingArea', pa_id)
                stop.set('duration', "30")
                trip_counter += 1

# ファイルに書き出し
rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(OUTPUT_POOL_FILE, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n生成完了: '{OUTPUT_POOL_FILE}' ({trip_counter}台)")
print("次に、このファイルを使ってduarouterを実行してください。")