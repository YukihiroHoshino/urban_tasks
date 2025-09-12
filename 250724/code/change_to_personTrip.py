import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import re
from copy import deepcopy

# 入力ファイルと出力ファイルの名前
input_file = '250724/data/thursday_added_v2_scenario_2.rou.xml'
output_file = '250724/data/thursday_added_v2_scenario_2_person_ex.rou.xml'

# ルート直下に挿入する vType / flow ブロック
vtype_text = '''\
<!-- VTypes -->
<vType id="DEFAULT_VEHTYPE"/>
<vType id="truck" vClass="truck"/>
<vType id="BUS" vClass="bus" length="12" width="2.5" maxSpeed="27" accel="2.0" decel="4.0" sigma="0.5" color="1,1,0"/>
  <flow id="busflow_1" type="BUS" begin="0" end="86399" line="line" from="128185375" to="128185375"
     via="447675894#1 447675894#1.32 -E19 -E18 -E17 -E16 -E16.17 E12 1231325642#0 1231325642#0.343 1231325642#1 1231325642#2 1231325646#0 1231325646#0.55 1231325646#1 1231325646#2 1231325647 1185697574#0 1185697574#1 1185697574#2 1185697574#3 951329849#1 951329849#2 951329849#3 951328429#0 951328429#1 169920326#0 169920326#1 169920326#2 169920326#3 169920326#4 1231325655#0 1231325655#0.62 1231325655#0.62.56 1231325655#1 1231325655#2 1231325664#0 E51 E70 E70.449 28184296#9 28184616 28111409 28184603#1 -E70.140.315 41247903#4 1231325662#1.41 1231325661#1 951329843 951329843.64 1231325643#1 1231325643#2"
   period="300.00" arrivalLane="2" departLaneChangeProhibited="true" arrivalLaneChangeProhibited="true">
    <stop busStop="bs_smartic" until="1"/>
	<stop busStop="bs_smartic2" until="1"/>
    <stop busStop="bs_sokaparkd" until="1"/>
    <stop busStop="bs_laketownd" until="1"/>
    <stop busStop="bs_laketownd2" until="1"/>
    <stop busStop="bs_laketownd3" until="1"/>
    <stop busStop="bs_ichigoparkd" until="1"/>
    <stop busStop="bs_techpoliced" until="1"/>
    <stop busStop="bs_toyonod" until="1"/>
    <stop busStop="bs_kasukabeaeond" until="1"/>
    <stop busStop="bs_kasukabeaeonu" until="1"/>
    <stop busStop="bs_toyonou" until="1"/>
    <stop busStop="bs_techpoliceu" until="1"/>
    <stop busStop="bs_ichigoparku" until="1"/>
    <stop busStop="bs_laketownu3" until="1"/>
    <stop busStop="bs_laketownu2" until="1"/>
    <stop busStop="bs_laketownu" until="1"/>
    <stop busStop="bs_sokaparku" until="1"/>
  </flow>

'''

def build_person_from_trip(trip: ET.Element) -> ET.Element:
    """車種指定なしの trip を person / personTrip に変換する."""
    person = ET.Element('person', {
        'id': trip.get('id', ''),
        'depart': trip.get('depart', '0'),
        'period': '1',
    })

    # 位置属性は元の形式を維持
    if trip.get('fromJunction') is not None or trip.get('toJunction') is not None:
        # fromJunction/toJunction ベース
        ptrip_attrs = {
            'fromJunction': trip.get('fromJunction', ''),
            'toJunction'  : trip.get('toJunction', ''),
            'modes'       : 'public car',
        }
    else:
        # from/to ベース（こちらがあるケース）
        ptrip_attrs = {
            'from'  : trip.get('from', ''),
            'to'    : trip.get('to', ''),
            'modes' : 'public car',
        }

    person_trip = ET.Element('personTrip', ptrip_attrs)
    person.append(person_trip)
    return person

def main():
    # 元XML読込
    tree = ET.parse(input_file)
    root_in = tree.getroot()

    # 新しい <routes>
    root_out = ET.Element('routes')

    # <routes> 直下に vType / flow を追加
    wrapper = ET.fromstring(f"<wrapper>{vtype_text}</wrapper>")
    for child in list(wrapper):
        root_out.append(child)

    # 各 trip を処理
    for trip in root_in.findall('trip'):
        trip_type = trip.get('type')

        if trip_type == 'truck':
            # 車種指定あり → そのまま（属性も保持）
            root_out.append(deepcopy(trip))
        else:
            # 車種指定なし → person / personTrip に変換
            root_out.append(build_person_from_trip(trip))

    # 整形して出力（インデントあり、空行なし）
    rough = ET.tostring(root_out, encoding='utf-8')
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")

    # 余分な空行を削除（要素間の空行をなくす）
    pretty = re.sub(r'\n\s*\n+', '\n', pretty)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty)

    print(f"変換・整形完了: {output_file}")

if __name__ == '__main__':
    main()
