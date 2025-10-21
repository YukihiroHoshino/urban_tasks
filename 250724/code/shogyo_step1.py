import xml.etree.ElementTree as ET
import sys
import pyproj

# --- 設定項目 ---
# 入力ファイルのパス
net_file = '250724/data/master_forResearch_fixed_bukai_step1_truck_jp_parking.net.xml'
input_rou_file = '250724/data/sunday_step1_dropped.rou.xml'

# 出力ファイルのパス
output_rou_file = '250724/data/sunday_step1_shogyo.rou.xml'

# --- ここからコード ---

def parse_net_file_and_convert_coords(file_path):
    """
    .net.xmlファイルを解析し、convBoundaryとorigBoundaryを用いた線形補間で
    平面座標を緯度経度に変換し、辞書を返す。
    """
    print(f"'{file_path}' を読み込んでいます...")
    junction_coords = {}
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # --- 1. <location> タグから境界情報を自動取得 ---
        location_tag = root.find('location')
        if location_tag is None:
            print("エラー: net.xmlファイルに<location>タグが見つかりません。")
            sys.exit(1)

        # convBoundaryから変換後の座標範囲を取得
        conv_boundary_str = location_tag.get('convBoundary')
        conv_min_x, conv_min_y, conv_max_x, conv_max_y = map(float, conv_boundary_str.split(','))
        
        # origBoundaryから元の緯度経度範囲を取得
        orig_boundary_str = location_tag.get('origBoundary')
        orig_min_lon, orig_min_lat, orig_max_lon, orig_max_lat = map(float, orig_boundary_str.split(','))
        
        print(f"変換元座標範囲(convBoundary): x=[{conv_min_x}, {conv_max_x}], y=[{conv_min_y}, {conv_max_y}]")
        print(f"変換先緯度経度範囲(origBoundary): lon=[{orig_min_lon}, {orig_max_lon}], lat=[{orig_min_lat}, {orig_max_lat}]")

        # --- 2. 線形補間のためのスケールを計算 ---
        conv_width = conv_max_x - conv_min_x
        conv_height = conv_max_y - conv_min_y
        orig_lon_width = orig_max_lon - orig_min_lon
        orig_lat_height = orig_max_lat - orig_min_lat
        
        # 幅や高さが0の場合はエラー
        if conv_width == 0 or conv_height == 0:
            print("エラー: convBoundaryの幅または高さが0です。")
            sys.exit(1)

        print("境界情報に基づき、線形補間で座標を変換しています...")
        
        # 検証のため、最初の5件の座標を表示するフラグ
        print_count = 0

        for junction in root.findall('junction'):
            junction_id = junction.get('id')
            if junction_id and not junction_id.startswith(':'):
                try:
                    # net.xmlから平面座標(x, y)を読み込む
                    x_proj = float(junction.get('x'))
                    y_proj = float(junction.get('y'))
                    
                    # 座標を0-1の範囲に正規化
                    x_norm = (x_proj - conv_min_x) / conv_width
                    y_norm = (y_proj - conv_min_y) / conv_height
                    
                    # 緯度経度の範囲にマッピング（線形補間）
                    lon_deg = orig_min_lon + x_norm * orig_lon_width
                    lat_deg = orig_min_lat + y_norm * orig_lat_height
                    
                    junction_coords[junction_id] = {'lat': lat_deg, 'lon': lon_deg}

                    # --- 検証用：最初の5件をコンソールに出力 ---
                    if print_count < 5:
                        print(f"  変換成功: ID={junction_id}, Lon={lon_deg:.6f}, Lat={lat_deg:.6f} (元のX={x_proj}, Y={y_proj})")
                        print_count += 1

                except (ValueError, TypeError, KeyError):
                    # 属性が不正な場合はスキップ
                    continue
        
        if print_count > 0:
             print("  ...")
        print(f"✅ {len(junction_coords)}個のジャンクション座標を正常に変換・読み込みました。")
        return junction_coords
        
    except FileNotFoundError:
        print(f"エラー: ネットワークファイル '{file_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ネットワークファイル '{file_path}' のXML形式が正しくありません。")
        sys.exit(1)
    except (ValueError, IndexError) as e:
        print(f"エラー: 境界情報(Boundary)の解析に失敗しました。詳細: {e}")
        sys.exit(1)


def process_rou_file(input_path, output_path, junction_coords):
    """
    .rou.xmlファイルを処理し、条件に基づいてトリップを駐車場停車を含むトリップに置き換える。
    """
    print(f"'{input_path}' の処理を開始します...")
    
    m1_counter = 0
    o1_counter = 0
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

            # 正しく変換された緯度経度を取得
            lat_origin = junction_coords[from_junction_id]['lat']
            lat_dest = junction_coords[to_junction_id]['lat']
            lon_dest = junction_coords[to_junction_id]['lon']
            
            # 目的地の座標が指定範囲内にあるかチェック
            if (35.868278 < lat_dest < 35.888212) and \
               (139.814485 < lon_dest < 139.834880):
                
                trips_to_remove.append(trip)
                
                original_depart = trip.get('depart')
                original_from = trip.get('fromJunction')
                original_type = trip.get('type')

                if lat_origin > 35.8837:
                    m1_counter += 1
                    new_trip_attrs = {
                        'id': f'laketown_m1_{m1_counter}',
                        'depart': original_depart,
                        'fromJunction': original_from,
                        'toJunction': '1810780648'
                    }
                    if original_type:
                        new_trip_attrs['type'] = original_type
                    
                    new_trip = ET.Element('trip', new_trip_attrs)
                    ET.SubElement(new_trip, 'stop', {'parkingArea': 'm1', 'duration': '7200'})
                    trips_to_add.append(new_trip)
                else:
                    o1_counter += 1
                    new_trip_attrs = {
                        'id': f'laketown_o1_{o1_counter}',
                        'depart': original_depart,
                        'fromJunction': original_from,
                        'toJunction': '3908775623'
                    }
                    if original_type:
                        new_trip_attrs['type'] = original_type

                    new_trip = ET.Element('trip', new_trip_attrs)
                    ET.SubElement(new_trip, 'stop', {'parkingArea': 'o1_1', 'duration': '7200'})
                    trips_to_add.append(new_trip)

        for trip in trips_to_remove:
            root.remove(trip)
        for trip in trips_to_add:
            root.append(trip)

        tree.write(output_path, encoding='UTF-8', xml_declaration=True)
        print(f"✅ 処理が完了しました。{len(trips_to_add)}件のトリップが駐車場停車に置き換えられました。")
        print(f"   内訳: 駐車場m1 = {m1_counter}件, 駐車場o1_1 = {o1_counter}件")
        print(f"新しいファイルが '{output_path}' に保存されました。")

    except FileNotFoundError:
        print(f"エラー: ルートファイル '{input_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ルートファイル '{input_path}' のXML形式が正しくありません。")
        sys.exit(1)


if __name__ == '__main__':
    # 1. netファイルからジャンクションのカスタム平面座標を読み込み、緯度経度に変換する
    junction_coordinates = parse_net_file_and_convert_coords(net_file)
    
    # 2. rouファイルを処理して新しいファイルを作成する
    if junction_coordinates:
        process_rou_file(input_rou_file, output_rou_file, junction_coordinates)