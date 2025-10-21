import xml.etree.ElementTree as ET
import sys

# --- 設定項目 ---
# 入力ファイルのパス
net_file = '250724/data/master_forResearch_fixed_bukai_step1_truck_jp_parking.net.xml'
input_rou_file = '250724/data/sunday_IC_dropped.rou.xml'

# 出力ファイルのパス
output_rou_file = '250724/data/sunday_IC_shogyo.rou.xml'

# --- ここからコード ---

def parse_net_file(file_path):
    """
    .net.xmlファイルを解析し、ジャンクションIDと座標の辞書を返す。
    SUMOのnet.xmlでは x が経度(longitude), y が緯度(latitude)に対応します。
    """
    print(f"'{file_path}' を読み込んでいます...")
    junction_coords = {}
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        for junction in root.findall('junction'):
            junction_id = junction.get('id')
            if junction_id and not junction_id.startswith(':'):
                try:
                    lon = float(junction.get('x'))
                    lat = float(junction.get('y'))
                    junction_coords[junction_id] = {'lat': lat, 'lon': lon}
                except (ValueError, TypeError):
                    continue
        print(f"✅ {len(junction_coords)}個のジャンクション座標を読み込みました。")
        return junction_coords
    except FileNotFoundError:
        print(f"エラー: ネットワークファイル '{file_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ネットワークファイル '{file_path}' のXML形式が正しくありません。")
        sys.exit(1)

def process_rou_file(input_path, output_path, junction_coords):
    """
    .rou.xmlファイルを処理し、条件に基づいてトリップを駐車場停車を含むトリップに置き換える。
    """
    print(f"'{input_path}' の処理を開始します...")
    
    # 新しいtrip IDのためのカウンター
    m1_counter = 0
    o1_counter = 0

    # ループ中に要素を安全に変更するため、削除・追加する要素をリストに保持
    trips_to_remove = []
    trips_to_add = []

    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
        
        for trip in root.findall('trip'):
            if trip.get('type') == 'truck':
                continue

            from_junction_id = trip.get('fromJunction')
            to_junction_id = trip.get('toJunction')

            if from_junction_id not in junction_coords or to_junction_id not in junction_coords:
                continue

            lat_origin = junction_coords[from_junction_id]['lat']
            lat_dest = junction_coords[to_junction_id]['lat']
            lon_dest = junction_coords[to_junction_id]['lon']
            
            # 目的地の座標が指定範囲内にあるかチェック
            if (35.868278 < lat_dest < 35.888212) and \
               (139.814485 < lon_dest < 139.834880):
                
                # このトリップは置き換え対象なので、削除リストに追加
                trips_to_remove.append(trip)
                
                # 元のトリップから共通の属性を取得
                original_depart = trip.get('depart')
                original_from = trip.get('fromJunction')

                # 出発地の緯度に基づいて新しいトリップを作成
                if lat_origin > 35.8837:
                    m1_counter += 1
                    # 新しいtrip要素を定義
                    new_trip_attrs = {
                        'id': f'laketown_m1_{m1_counter}',
                        'depart': original_depart,
                        'fromJunction': original_from,
                        'toJunction': '1810780648'
                    }
                    
                    new_trip = ET.Element('trip', new_trip_attrs)

                    # stopサブ要素を追加
                    ET.SubElement(new_trip, 'stop', {
                        'parkingArea': 'm1',
                        'duration': '7200'
                    })
                    trips_to_add.append(new_trip)

                else: # lat_origin <= 35.8837
                    o1_counter += 1
                    # 新しいtrip要素を定義
                    new_trip_attrs = {
                        'id': f'laketown_o1_{o1_counter}',
                        'depart': original_depart,
                        'fromJunction': original_from,
                        'toJunction': '3908775623'
                    }

                    new_trip = ET.Element('trip', new_trip_attrs)

                    # stopサブ要素を追加
                    ET.SubElement(new_trip, 'stop', {
                        'parkingArea': 'o1_1',
                        'duration': '7200'
                    })
                    trips_to_add.append(new_trip)

        # --- ループ完了後にXMLツリーをまとめて更新 ---
        for trip in trips_to_remove:
            root.remove(trip)
        
        for trip in trips_to_add:
            root.append(trip)

        # 変更をファイルに書き込む
        tree.write(output_path, encoding='UTF-8', xml_declaration=True)
        print(f"✅ 処理が完了しました。{len(trips_to_add)}件のトリップが駐車場停車に置き換えられました。")
        print(f"   内訳: laketown_m1 (駐車場m1) = {m1_counter}件, laketown_o1 (駐車場o1_1) = {o1_counter}件")
        print(f"新しいファイルが '{output_path}' に保存されました。")

    except FileNotFoundError:
        print(f"エラー: ルートファイル '{input_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ルートファイル '{input_path}' のXML形式が正しくありません。")
        sys.exit(1)


if __name__ == '__main__':
    # 1. netファイルからジャンクションの座標を読み込む
    junction_coordinates = parse_net_file(net_file)
    
    # 2. rouファイルを処理して新しいファイルを作成する
    if junction_coordinates: # 座標が正常に読み込めた場合のみ実行
        process_rou_file(input_rou_file, output_rou_file, junction_coordinates)