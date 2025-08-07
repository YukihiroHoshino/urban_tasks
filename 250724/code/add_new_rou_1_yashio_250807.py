# generate_trip_pool.py
import xml.etree.ElementTree as ET
import numpy as np
import itertools

# --- 設定 ---
# duarouterで検証後、各ペアから十分にサンプリングできるだけの数を生成します
NUM_TRIPS_PER_PAIR = 3000
EDG_FILE_PATH = '250724/data/example.edg.xml'
OUTPUT_POOL_FILE = '250724/data/example_additional_trips_pool.rou.xml'

# --- 全シナリオのトリップ定義をここに集約 ---
# このスクリプトでは、これらのリストからユニークなODペアを抽出するためにのみ使用します
all_lists = {
    "L1": [
        ["128185343", "Anywhere"], ["1231325634#1", "Anywhere"],
        ["Anywhere", "128185343"], ["Anywhere", "1231325634#1"],
        ["314943854#8", "Anywhere"], ["Anywhere", "314943854#8"],
        ["-314943854#4", "Anywhere"], ["314943854#4.70", "Anywhere"],
        ["Anywhere", "-314943854#4"], ["Anywhere", "314943854#4.70"],
        ["628774981#1", "Anywhere"], ["Anywhere", "628774981#1"],
        ["-732836013#5", "Anywhere"], ["Anywhere", "-732836013#5"]
    ],
    "L211": [
        ["128185343", "Anywhere"], ["1231325634#1", "Anywhere"],
        ["Anywhere", "128185343"], ["Anywhere", "1231325634#1"]
    ],
    "L212": [
        ["128185343", "Anywhere"], ["1231325634#1", "Anywhere"],
        ["Anywhere", "128185343"], ["Anywhere", "1231325634#1"]
    ],
    "L221": [
        ["E12.164", "Anywhere"], ["1231325634#3", "Anywhere"],
        ["Anywhere", "E12.164"], ["Anywhere", "1231325634#3"]
    ],
    "L222": [
        ["E12.164", "Anywhere"], ["1231325634#3", "Anywhere"],
        ["Anywhere", "E12.164"], ["Anywhere", "1231325634#3"]
    ],
    "L231": [
        ["-314943854#4", "Anywhere"], ["314943854#4.70", "Anywhere"],
        ["Anywhere", "-314943854#4"], ["Anywhere", "314943854#4.70"]
    ],
    "L232": [
        ["-314943854#4", "Anywhere"], ["314943854#4.70", "Anywhere"],
        ["Anywhere", "-314943854#4"], ["Anywhere", "314943854#4.70"]
    ]
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

# 全リストからユニークなODペア定義を抽出
unique_od_pairs = set()
for list_name, demand_list in all_lists.items():
    for o, d in demand_list:
        unique_od_pairs.add((o, d, list_name))

print(f"ユニークなODペア定義を {len(unique_od_pairs)} 件見つけました。")
print(f"各ペアについて {NUM_TRIPS_PER_PAIR} 台のトリップを生成します...")

rou_root = ET.Element('routes')

# ユニークなODペアごとに多数のトリップを生成
pair_counter = 0
for o_base, d_base, list_name_hint in unique_od_pairs:
    for j in range(NUM_TRIPS_PER_PAIR):
        # O/Dが同一にならないようにする
        while True:
            o, d = o_base, d_base
            if o == "Anywhere": o = np.random.choice(edg_list)
            if d == "Anywhere": d = np.random.choice(edg_list)
            if o != d: break
        
        # IDにどの定義から来たものかを含める (例: L1_0, L211_1)
        # 実際のリスト内のインデックスは後段で使うので、ここではペアの一意性を担保するIDとする
        trip_id = f"pool_{pair_counter}_{j}"
        
        trip = ET.SubElement(rou_root, 'trip')
        # ID, from, to が重要。depart, typeはダミーでOK
        trip.set('id', trip_id)
        trip.set('depart', "0")
        trip.set('from', o)
        trip.set('to', d)
    pair_counter += 1

# ファイルに書き出し
rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(OUTPUT_POOL_FILE, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n生成完了: '{OUTPUT_POOL_FILE}'")
print("次に、このファイルを使ってduarouterを実行してください。")