import xml.etree.ElementTree as ET
from collections import defaultdict

# 入力XMLファイルパス
xml_file = "250724/data/sunday_yashio_added_scenario_7.rou.xml"

# XML解析
tree = ET.parse(xml_file)
root = tree.getroot()

id_count = defaultdict(list)

# すべての要素を走査して id 属性を収集
for elem in root.iter():
    if "id" in elem.attrib:
        elem_id = elem.attrib["id"]
        id_count[elem_id].append(elem)

# 重複IDを検出
duplicates = {id_: elems for id_, elems in id_count.items() if len(elems) > 1}

# 結果出力
if duplicates:
    print("重複している ID:")
    for id_, elems in duplicates.items():
        print(f"- ID: {id_} (出現回数: {len(elems)})")
else:
    print("重複IDはありません。")
