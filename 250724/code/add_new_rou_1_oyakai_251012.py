import xml.etree.ElementTree as ET
import numpy as np
import sys

# --- 設定 ---
# .net.xmlファイルのパスを指定してください
NET_FILE_PATH = '250724/data/master_forResearch_fixed_genBRT_0903_truck_jp.net.xml'
# 出力するトリップファイルのパスを指定してください
OUTPUT_POOL_FILE = '250724/data/oyakai_additional_trips_pool.rou.xml'

# --- 生成する往復トリップの定義 ---
# 各定義は (固定ジャンクションID, 生成する往復ペアの数) のタプルで指定します
TRIP_PAIRS = [
    ("309574569", 15000), #赤沼銚子口地区産業団地
    ("3909015091", 25000), #
    ("6313710997", 2000), #
    ("J287", 3000), #
]

def indent(elem, level=0):
    """
    XML要素をきれいにインデントするためのヘルパー関数
    """
    i = '\n' + level * '  '
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + '  '
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for el in elem:
            indent(el, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

# --- メイン処理 ---
print("--- 往復トリップ生成スクリプト開始 ---")

# 1. .net.xmlファイルからジャンクションリストを読み込む
try:
    net_xml = ET.parse(NET_FILE_PATH).getroot()
    # 'internal'タイプのジャンクションはO/D地点として不適切なため除外する
    junction_list = [
        j.attrib['id'] for j in net_xml.findall('junction')
        if j.attrib.get('type') != 'internal'
    ]
    if not junction_list:
        print(f"エラー: {NET_FILE_PATH} に有効なジャンクションが見つかりません。")
        sys.exit()
    print(f"{len(junction_list)} 件のジャンクションを読み込みました。")
except FileNotFoundError:
    print(f"エラー: ネットワークファイルが見つかりません: {NET_FILE_PATH}")
    sys.exit()
except ET.ParseError:
    print(f"エラー: {NET_FILE_PATH} のXMLパースに失敗しました。")
    sys.exit()


# 2. 往復トリップを生成
rou_root = ET.Element('routes')
total_trips_generated = 0

print("トリップの生成を開始します...")

for fixed_junction, num_pairs in TRIP_PAIRS:
    print(f"  - ペア定義: {fixed_junction}, {num_pairs}往復ペア")

    # 固定ジャンクションがリストに存在するか確認
    if fixed_junction not in junction_list:
        print(f"    警告: 固定ジャンクション '{fixed_junction}' がネットワーク内に見つかりません。この定義をスキップします。")
        continue

    for i in range(num_pairs):
        # 出発地と目的地が同一にならないようにランダムなジャンクションを1つ選択
        while True:
            random_junction = np.random.choice(junction_list)
            if random_junction != fixed_junction:
                break

        # --- 往路トリップ (ランダム -> 固定) を生成 ---
        to_trip_id = f"additional_oyakai_trip_{total_trips_generated}"
        to_trip = ET.SubElement(rou_root, 'trip')
        to_trip.set('id', to_trip_id)
        to_trip.set('depart', "0")
        to_trip.set('fromJunction', random_junction)
        to_trip.set('toJunction', fixed_junction)
        total_trips_generated += 1
        
        # --- 復路トリップ (固定 -> ランダム) を生成 ---
        from_trip_id = f"additional_oyakai_trip_{total_trips_generated}"
        from_trip = ET.SubElement(rou_root, 'trip')
        from_trip.set('id', from_trip_id)
        from_trip.set('depart', "0")
        from_trip.set('fromJunction', fixed_junction)
        from_trip.set('toJunction', random_junction)
        total_trips_generated += 1

# 3. XMLファイルに書き出し
rou_tree = ET.ElementTree(rou_root)
indent(rou_root)
with open(OUTPUT_POOL_FILE, 'wb') as file:
    rou_tree.write(file, encoding='utf-8', xml_declaration=True)

print(f"\n--- トリップ生成完了 ---")
# 各ペアで2つのトリップ（往路・復路）が生成されるため、合計数は2倍になる
print(f"合計 {total_trips_generated} 件のトリップ（{total_trips_generated // 2} 往復ペア）を生成しました。")
print(f"出力ファイル: '{OUTPUT_POOL_FILE}'")