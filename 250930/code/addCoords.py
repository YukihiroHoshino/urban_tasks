import pandas as pd
import xml.etree.ElementTree as ET
from tqdm import tqdm

def parse_edge_xml_to_coords(edg_xml_path):
    """
    SUMOのedge.xmlファイルを解析し、各エッジの始点と終点の座標を辞書として返す。

    Args:
        edg_xml_path (str): .edg.xmlファイルのパス。

    Returns:
        tuple: (edge_start_coords, edge_end_coords)
               - edge_start_coords: {edge_id: (lon, lat), ...}
               - edge_end_coords: {edge_id: (lon, lat), ...}
    """
    print(f"'{edg_xml_path}' を解析しています...")
    tree = ET.parse(edg_xml_path)
    root = tree.getroot()

    edge_start_coords = {}
    edge_end_coords = {}

    for edge in tqdm(root.findall('edge'), desc="Edgeファイルを処理中"):
        edge_id = edge.get('id')
        shape = edge.get('shape')

        if edge_id and shape:
            # shape属性は "lon,lat lon,lat ..." の形式
            coords = shape.split(' ')
            start_coord_str = coords[0].split(',')
            end_coord_str = coords[-1].split(',')

            try:
                # 始点の緯度経度をfloatに変換して格納
                start_lon, start_lat = float(start_coord_str[0]), float(start_coord_str[1])
                edge_start_coords[edge_id] = (start_lon, start_lat)

                # 終点の緯度経度をfloatに変換して格納
                end_lon, end_lat = float(end_coord_str[0]), float(end_coord_str[1])
                edge_end_coords[edge_id] = (end_lon, end_lat)
            except (ValueError, IndexError):
                print(f"警告: Edge '{edge_id}' の座標形式が無効です。スキップします。")

    print("Edgeファイルの解析が完了しました。")
    return edge_start_coords, edge_end_coords


# --- メイン処理 ---

# 1. ファイルパスの設定
tripinfo_csv_path = '250930/data/tripinfo_BRT.csv'
edge_xml_path = '250724/data/edge_BRT.edg.xml'
output_csv_path = '250930/data/tripinfo_with_coords_BRT.csv'

# 2. Edge XMLから座標辞書を作成
start_coords_dict, end_coords_dict = parse_edge_xml_to_coords(edge_xml_path)

# 3. Tripinfo CSVを読み込む
print(f"'{tripinfo_csv_path}' を読み込んでいます...")
df_trips = pd.read_csv(tripinfo_csv_path)

# 4. 座標をマッピング
# ヘルパー関数を定義
def get_coord(lane_id, coord_dict, index):
    """lane_idからedge_idを抽出し、辞書から座標を取得する"""
    if pd.isna(lane_id):
        return None
    # 'edgeID_laneIndex' 形式から '_laneIndex' を除去
    edge_id = lane_id.split('_')[0]
    # 辞書に存在しない場合もエラーにならないように .get を使用
    return coord_dict.get(edge_id, (None, None))[index]

print("トリップデータに緯度経度をマッピングしています...")
# tqdmをpandasのapplyに適用するため、progress_applyを登録
tqdm.pandas(desc="座標をマッピング中")

# 出発地の緯度経度を追加
df_trips['depart_lon'] = df_trips['departLane'].progress_apply(get_coord, args=(start_coords_dict, 0))
df_trips['depart_lat'] = df_trips['departLane'].progress_apply(get_coord, args=(start_coords_dict, 1))

# 到着地の緯度経度を追加
df_trips['arrival_lon'] = df_trips['arrivalLane'].progress_apply(get_coord, args=(end_coords_dict, 0))
df_trips['arrival_lat'] = df_trips['arrivalLane'].progress_apply(get_coord, args=(end_coords_dict, 1))

# 5. 結果を新しいCSVファイルに保存
print(f"処理が完了しました。結果を '{output_csv_path}' に保存します。")
df_trips.to_csv(output_csv_path, index=False)

# 結果の確認
print("\n--- 処理後のデータ（先頭5行） ---")
print(df_trips.head())