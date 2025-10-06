import xml.etree.ElementTree as ET
from collections import Counter
import folium
from tqdm import tqdm
import os

def parse_edge_xml_to_coords(edg_xml_path):
    """
    SUMOのedge.xmlファイルを解析し、各エッジの始点と終点の座標を辞書として返す。
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
            coords = shape.split(' ')
            start_coord_str = coords[0].split(',')
            end_coord_str = coords[-1].split(',')
            try:
                start_lon, start_lat = float(start_coord_str[0]), float(start_coord_str[1])
                edge_start_coords[edge_id] = (start_lon, start_lat)
                end_lon, end_lat = float(end_coord_str[0]), float(end_coord_str[1])
                edge_end_coords[edge_id] = (end_lon, end_lat)
            except (ValueError, IndexError):
                print(f"警告: Edge '{edge_id}' の座標形式が無効です。スキップします。")

    print("Edgeファイルの解析が完了しました。")
    return edge_start_coords, edge_end_coords

def analyze_and_map_delays(tripinfo_xml, edge_xml, delay_threshold=30000, output_html='delayed_trips_map.html'):
    """
    tripinfoを解析し、指定した遅延以上のトリップの出発点を地図上にプロットする。
    """
    # 1. Edgeファイルの座標を読み込む
    edge_coords, _ = parse_edge_xml_to_coords(edge_xml)
    if not edge_coords:
        print("エラー: Edge座標が読み込めませんでした。")
        return

    # 2. Tripinfoファイルを解析し、遅延の大きいトリップの出発edgeをカウント
    print(f"'{tripinfo_xml}' を解析しています...")
    tree = ET.parse(tripinfo_xml)
    root = tree.getroot()
    
    delayed_trip_edges = []
    for trip in tqdm(root.findall('tripinfo'), desc="Tripinfoファイルを処理中"):
        try:
            delay = float(trip.get('departDelay', 0))
            if delay >= delay_threshold:
                depart_lane = trip.get('departLane')
                if depart_lane:
                    # departLane (e.g., "-277743732#1_1") から edge ID ("-277743732#1") を抽出
                    edge_id = depart_lane.rpartition('_')[0]
                    delayed_trip_edges.append(edge_id)
        except (ValueError, TypeError):
            # departDelayが数値でない場合はスキップ
            continue
            
    if not delayed_trip_edges:
        print(f"departDelayが{delay_threshold}以上のトリップは見つかりませんでした。")
        return

    edge_counts = Counter(delayed_trip_edges)
    print("\n遅延が発生したEdgeとその回数:")
    for edge, count in edge_counts.items():
        print(f"  - Edge ID: {edge}, 回数: {count}")

    # 3. 地図を作成してプロット
    # 地図の中心を最初の座標に設定
    first_edge_id = list(edge_counts.keys())[0]
    center_lon, center_lat = edge_coords.get(first_edge_id, (139.82476280562, 35.877664063142))
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    print("\n地図上にプロットしています...")
    for edge_id, count in tqdm(edge_counts.items(), desc="マッピング中"):
        coords = edge_coords.get(edge_id)
        if coords:
            lon, lat = coords
            # 半径を回数に応じて変更 (基本半径 + 回数に応じた増加分)
            radius = 3 + count * 0.001
            
            popup_text = f"<b>Edge ID:</b> {edge_id}<br><b>遅延トリップ数:</b> {count}"
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color='crimson',
                fill=True,
                fill_color='crimson',
                fill_opacity=0.6,
                popup=folium.Popup(popup_text, max_width=300)
            ).add_to(m)

    # 4. HTMLファイルとして保存
    m.save(output_html)
    print(f"\n完了しました！地図が '{output_html}' として保存されました。")

# --- メイン処理 ---
if __name__ == "__main__":
    TRIPINFO_FILE = "251006/data/tripinfo_3_thursday.xml"
    EDGE_FILE = "250724/data/edge_IC.edg.xml"
    OUTPUT_MAP_FILE = "251006/fig/large_delay_departures_map.html"
    
    analyze_and_map_delays(TRIPINFO_FILE, EDGE_FILE, output_html=OUTPUT_MAP_FILE)