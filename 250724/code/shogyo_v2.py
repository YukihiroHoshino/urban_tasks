import xml.etree.ElementTree as ET
import sys
import csv
import random # 駐車場のランダム割り当てに使用
import xml.dom.minidom # XMLの整形出力（Pretty Print）に使用

# --- 設定項目 ---
# (mainブロックに移動しました)

def parse_nod_file(file_path):
    """
    .nod.xmlファイルを解析し、ノードIDと座標の辞書を返す。
    SUMOのnod.xmlでは x が経度(longitude), y が緯度(latitude)に対応します。
    """
    print(f"'{file_path}' を読み込んでいます...")
    node_coords = {}
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        # <junction> の代わりに <node> を探す
        for node in root.findall('node'):
            node_id = node.get('id')
            if node_id:
                try:
                    lon = float(node.get('x'))
                    lat = float(node.get('y'))
                    node_coords[node_id] = {'lat': lat, 'lon': lon}
                except (ValueError, TypeError):
                    continue
        print(f"✅ {len(node_coords)}個のノード座標を読み込みました。")
        return node_coords
    except FileNotFoundError:
        print(f"エラー: ノードファイル '{file_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ノードファイル '{file_path}' のXML形式が正しくありません。")
        sys.exit(1)

def parse_shogyo_csv(file_path):
    """
    shogyo.csvファイルを解析し、場所ごとのターゲット情報を辞書として返す。
    KoshigayaLakeTown は例外ロジックで処理するため、この関数ではスキップする。
    """
    print(f"'{file_path}' を読み込んでいます...")
    shogyo_targets = {}
    
    # 指定された緯度・経度の範囲
    lat_delta = 0.009454
    lon_delta = 0.010271
    
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                header = next(reader) # ヘッダーをスキップ
            except StopIteration:
                print(f"エラー: 商業施設ファイル '{file_path}' が空です。")
                return None
                
            for row in reader:
                # CSVの列が不足していないかチェック
                if len(row) < 6:
                    print(f"警告: CSVファイル '{file_path}' の行 {row} は列数が不足しているためスキップします。")
                    continue
                    
                place = row[0]
                
                # KoshigayaLakeTown は既存のロジックで処理するためスキップ
                if place == 'KoshigayaLakeTown':
                    continue
                
                try:
                    lat = float(row[1])
                    lon = float(row[2])
                    parking = row[3]
                    duration = row[4]
                    destination = row[5]
                except ValueError:
                    print(f"警告: CSVファイル '{file_path}' の行 {row} は数値形式が正しくないためスキップします。")
                    continue
                
                # 駐車場、滞在時間、目的地Junctionの情報を辞書に格納
                target_info = {
                    'parking': parking,
                    'duration': duration,
                    'destination': destination
                }
                
                if place not in shogyo_targets:
                    # この場所が辞書に初めて現れた場合
                    # 中心座標から緯度・経度の範囲を計算
                    shogyo_targets[place] = {
                        'lat_min': lat - lat_delta,
                        'lat_max': lat + lat_delta,
                        'lon_min': lon - lon_delta,
                        'lon_max': lon + lon_delta,
                        'targets': [target_info] # 最初のターゲット情報をリストに追加
                    }
                else:
                    # 既存の場所の場合 (例: aeontownYoshikawa の2行目以降)
                    # ターゲットリストに情報を追加
                    shogyo_targets[place]['targets'].append(target_info)
                    
        print(f"✅ {len(shogyo_targets)}箇所の商業施設（LakeTown除く）の集約情報を読み込みました。")
        for place, data in shogyo_targets.items():
            print(f"   - {place}: {len(data['targets'])}個の駐車場オプション")
        return shogyo_targets
        
    except FileNotFoundError:
        print(f"エラー: 商業施設ファイル '{file_path}' が見つかりません。")
        sys.exit(1)
    except Exception as e:
        print(f"エラー: 商業施設ファイル '{file_path}' の読み込み中にエラーが発生しました: {e}")
        sys.exit(1)

def process_rou_file(input_path, output_path, node_coords, shogyo_targets):
    """
    .rou.xmlファイルを処理し、条件に基づいてトリップを駐車場停車を含むトリップに置き換える。
    """
    print(f"'{input_path}' の処理を開始します...")
    
    # KoshigayaLakeTown 用のカウンター
    m1_counter = 0
    o1_counter = 0
    # その他の商業施設用のカウンター (場所名をキーとする辞書)
    place_counters = {}
    total_trips_processed = 0 # 処理件数をカウント
    
    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
        
        # findall の結果をイテレートすることで、順序を維持しつつ変更する
        trips_in_file = root.findall('trip')
        print(f"合計 {len(trips_in_file)}件のトリップをチェックします...")
        
        for trip in trips_in_file:
            if trip.get('type') == 'truck':
                continue
                
            from_junction_id = trip.get('fromJunction')
            to_junction_id = trip.get('toJunction')

            if from_junction_id not in node_coords or to_junction_id not in node_coords:
                continue
            
            lat_origin = node_coords[from_junction_id]['lat']
            lat_dest = node_coords[to_junction_id]['lat']
            lon_dest = node_coords[to_junction_id]['lon']
            
            # --- 1. KoshigayaLakeTown (既存の例外ロジック) ---
            # KoshigayaLakeTown のみ、ハードコードされた座標範囲でチェック
            if (35.868278 < lat_dest < 35.888212) and \
               (139.814485 < lon_dest < 139.834880):
                
                # 出発地の緯度 > 35.8837 に基づいて分岐
                if lat_origin > 35.8837:
                    m1_counter += 1
                    # 属性を直接変更
                    trip.set('id', f'laketown_m1_{m1_counter}')
                    trip.set('toJunction', '1810780648') # m1 駐車場対応
                    # 既存のstopをクリアしてから追加
                    for stop in trip.findall('stop'):
                        trip.remove(stop)
                    ET.SubElement(trip, 'stop', {'parkingArea': 'm1', 'duration': '7200'})
                else: # lat_origin <= 35.8837
                    o1_counter += 1
                    # 属性を直接変更
                    trip.set('id', f'laketown_o1_{o1_counter}')
                    trip.set('toJunction', '3908775623') # o1 駐車場対応
                    # 既存のstopをクリアしてから追加
                    for stop in trip.findall('stop'):
                        trip.remove(stop)
                    # 既存コードの 'o1_1' を維持
                    ET.SubElement(trip, 'stop', {'parkingArea': 'o1_1', 'duration': '7200'}) 
                
                total_trips_processed += 1
                continue # このトリップの処理は完了

            # --- 2. その他の商業施設 (shogyo.csv に基づく汎用ロジック) ---
            # found_target = False # <-- 不要
            # shogyo_targets 辞書（LakeTown除く）をループ
            for place_name, data in shogyo_targets.items():
                # 目的地がこの商業施設の範囲内かチェック
                if (data['lat_min'] <= lat_dest <= data['lat_max']) and \
                   (data['lon_min'] <= lon_dest <= data['lon_max']):
                    
                    # trips_to_remove.append(trip) # <-- 削除
                    
                    # この場所のカウンターをインクリメント
                    place_counters[place_name] = place_counters.get(place_name, 0) + 1
                    counter = place_counters[place_name]
                    
                    # この場所の駐車場のリスト (data['targets']) からランダムに1つを選択
                    selected_target = random.choice(data['targets'])
                    
                    # 属性を直接変更
                    trip.set('id', f'{place_name}_{counter}')
                    trip.set('toJunction', selected_target['destination'])
                    
                    # 既存のstopをクリアしてから追加
                    for stop in trip.findall('stop'):
                        trip.remove(stop)
                    ET.SubElement(trip, 'stop', {
                        'parkingArea': selected_target['parking'],
                        'duration': selected_target['duration']
                    })
                    
                    total_trips_processed += 1
                    break # 1つのトリップは1つの場所のみに割り当てる

        # --- ループ完了後にXMLツリーをまとめて更新 ---
        print(f"XMLツリーの {total_trips_processed}件のトリップをインプレース（in-place）で更新しました。")
        

        # --- XMLの整形 (Pretty Print) ---
        print("XMLを整形しています...")
        try:
            # Python 3.9+ の indent 機能
            ET.indent(tree, space="  ")
            print("ET.indent() による整形が完了しました。")
            # 整形されたツリーをファイルに書き込む
            tree.write(output_path, encoding='UTF-8', xml_declaration=True)
            
        except AttributeError:
            # Python 3.8 以前のフォールバック (minidom を使用)
            print("警告: ET.indent が利用できません (Python 3.9+ が必要)。minidomでの整形を試みます。")
            try:
                # ElementTree -> string -> minidom -> pretty string
                rough_string = ET.tostring(root, 'utf-8')
                reparsed = xml.dom.minidom.parseString(rough_string)
                pretty_xml_as_string = reparsed.toprettyxml(indent="  ", encoding='UTF-8')
                
                # minidom は <?xml ...?> ヘッダーを追加するので、ファイルに直接書き込む
                with open(output_path, "wb") as f:
                    f.write(pretty_xml_as_string)
                print("minidom による整形が完了しました。")

            except Exception as e_pretty:
                print(f"エラー: minidom でのXML整形に失敗しました: {e_pretty}")
                print("整形されていないXMLを書き込みます。")
                # 整形失敗時は、元の tree.write を実行
                tree.write(output_path, encoding='UTF-8', xml_declaration=True)
        
        # --- 集計結果の表示 ---
        print(f"✅ 処理が完了しました。合計 {total_trips_processed}件のトリップが駐車場停車に置き換えられました。")
        print(f"   --- 内訳 ---")
        print(f"   [例外] KoshigayaLakeTown (m1): {m1_counter}件")
        print(f"   [例外] KoshigayaLakeTown (o1_1): {o1_counter}件")
        
        total_other = 0
        for place_name, count in sorted(place_counters.items()): # 場所名でソートして表示
            print(f"   [CSV] {place_name}: {count}件")
            total_other += count
        
        print(f"   ----------------")
        print(f"   合計 (LakeTown): {m1_counter + o1_counter}件")
        print(f"   合計 (その他CSV): {total_other}件")
        print(f"   総合計: {m1_counter + o1_counter + total_other}件")
        print(f"新しいファイルが '{output_path}' に保存されました。")

    except FileNotFoundError:
        print(f"エラー: ルートファイル '{input_path}' が見つかりません。")
        sys.exit(1)
    except ET.ParseError:
        print(f"エラー: ルートファイル '{input_path}' のXML形式が正しくありません。")
        sys.exit(1)
    except Exception as e:
        print(f"エラー: ルートファイル '{input_path}' の処理中に予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # --- 設定項目 ---
    # 入力ファイルのパス
    nod_file = '250724/data/node_IC_shogyo.nod.xml'
    input_rou_file = '250724/data/sunday_IC_dropped.rou.xml'
    shogyo_csv_file = '250724/data/shogyo.csv' # 添付されたCSVファイル
    
    # 出力ファイルのパス
    output_rou_file = '250724/data/sunday_IC_shogyo.rou.xml'

    # 1. nodファイルからノードの座標を読み込む
    node_coordinates = parse_nod_file(nod_file)
    
    # 2. shogyo.csv から商業施設のターゲット情報を読み込む
    shogyo_targets = parse_shogyo_csv(shogyo_csv_file)
    
    # 3. rouファイルを処理して新しいファイルを作成する
    #    両方のファイル読み込みが成功した場合のみ実行
    if node_coordinates and shogyo_targets is not None: 
        process_rou_file(input_rou_file, output_rou_file, node_coordinates, shogyo_targets)
    else:
        print("エラー: 必要なファイル（nodまたはshogyo.csv）の読み込みに失敗したため、処理を中断しました。")