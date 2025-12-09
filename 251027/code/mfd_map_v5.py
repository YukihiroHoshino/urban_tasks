import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import folium
import io
import base64
import os
from scipy.stats import hmean
from pyproj import Transformer, CRS
import warnings
from collections import defaultdict
import japanize_matplotlib

# --- 1. 設定項目 ---
FILE_PATHS = {
    'net_step1': '251027/data/master_forResearch_fixed_bukai_step1_truck_jp_parking.net.xml',
    'net_step4': '251027/data/master_forResearch_fixed_bukai_step4_truck_jp_parking.net.xml',
    'step1_fcd': '251027/data/sunday_step1_fcd.xml',
    'step4_fcd': '251027/data/sunday_step4_fcd.xml'
}
OUTPUT_HTML = '251027/fig/mfd_comparison_map_18by15.html'

# MFD計算設定
MESH_ROWS = 18
MESH_COLS = 15
TIME_INTERVAL = 300  # 5分 (秒)

# グラフの時間範囲設定 (秒)
TIME_RANGE_MIN = 6 * 3600   # 6時
TIME_RANGE_MAX = 20 * 3600  # 20時

# --- 2. 補助関数 ---

def get_net_info(net_file):
    """netファイルから座標範囲、CRS情報、元の境界情報を解析する"""
    print(f"'{net_file}' を解析中...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    location = root.find('location')
    
    conv_boundary = [float(x) for x in location.attrib['convBoundary'].split(',')]
    orig_boundary = [float(x) for x in location.attrib['origBoundary'].split(',')]
    proj_param = location.attrib['projParameter']
    
    return {
        'bounds': tuple(conv_boundary),
        'orig_bounds': tuple(orig_boundary),
        'proj_param': proj_param
    }

def create_meshes(bounds, rows, cols):
    """メッシュを作成し、インデックス情報を追加する"""
    min_x, min_y, max_x, max_y = bounds
    mesh_width = (max_x - min_x) / cols
    mesh_height = (max_y - min_y) / rows
    
    meshes = []
    for i in range(rows):
        for j in range(cols):
            mesh_name = f"mesh_{rows-i}_{j+1}"
            m_min_y = min_y + i * mesh_height
            m_max_y = min_y + (i + 1) * mesh_height
            m_min_x = min_x + j * mesh_width
            m_max_x = min_x + (j + 1) * mesh_width
            meshes.append({
                'name': mesh_name,
                'bounds': (m_min_x, m_min_y, m_max_x, m_max_y),
                'row': rows - 1 - i,
                'col': j
            })
    print(f"{rows}x{cols} のメッシュを作成しました。")
    return meshes

def get_mesh_for_coord(x, y, meshes):
    """座標が属するメッシュの名前を返す"""
    for mesh in meshes:
        min_x, min_y, max_x, max_y = mesh['bounds']
        if min_x <= x < max_x and min_y <= y < max_y:
            return mesh['name']
    return None

def calculate_total_edge_lengths(net_file, meshes):
    """netファイルからメッシュごとの道路総延長[km]を計算する"""
    print(f"'{net_file}' から道路延長を計算中...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    
    mesh_lengths = defaultdict(float)
    
    for edge in root.findall('edge'):
        if 'shape' in edge.attrib:
            shape_str = edge.attrib['shape']
            points = [tuple(map(float, p.split(','))) for p in shape_str.split(' ')]
            
            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i+1]
                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
                length_m = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                mesh_name = get_mesh_for_coord(mid_x, mid_y, meshes)
                if mesh_name:
                    mesh_lengths[mesh_name] += length_m
                    
    mesh_lengths_km = {name: length / 1000.0 for name, length in mesh_lengths.items()}
    print("道路延長の計算が完了しました。")
    return mesh_lengths_km

def process_fcd_file(fcd_file, meshes):
    """FCDファイルを解析し、メッシュ・時間帯ごとの車両データを集計する"""
    print(f"'{fcd_file}' を処理中...")
    data = defaultdict(lambda: defaultdict(lambda: {'speeds': [], 'vehicle_counts_per_ts': defaultdict(int)}))
    
    try:
        context = ET.iterparse(fcd_file, events=('end',))
        for _, elem in context:
            if elem.tag == 'timestep':
                time = float(elem.attrib['time'])
                time_slot = int(time / TIME_INTERVAL) * TIME_INTERVAL
                
                for vehicle in elem:
                    if vehicle.tag == 'vehicle':
                        x = float(vehicle.attrib['x'])
                        y = float(vehicle.attrib['y'])
                        mesh_name = get_mesh_for_coord(x, y, meshes)
                        if mesh_name:
                            speed = float(vehicle.attrib['speed'])
                            data[mesh_name][time_slot]['speeds'].append(speed)
                            data[mesh_name][time_slot]['vehicle_counts_per_ts'][time] += 1
                elem.clear()
    except ET.ParseError as e:
        if "no element found" in str(e):
            warnings.warn(f"\n警告: '{fcd_file}' の解析中にXML構文エラー。ファイルが不完全な可能性がありますが、処理を続行します。")
        else:
            raise e
    return data

def calculate_mfd(processed_data, mesh_edge_lengths):
    """道路延長[km]を用いてMFDを計算する"""
    mfd_results = defaultdict(lambda: {'K': [], 'Q': [], 'time': []})

    for mesh_name, time_slots in processed_data.items():
        total_length_km = mesh_edge_lengths.get(mesh_name, 0)
        if total_length_km == 0:
            continue

        for time_slot, values in sorted(time_slots.items()): # 時間順に処理
            if not (TIME_RANGE_MIN <= time_slot < TIME_RANGE_MAX):
                continue

            counts = values['vehicle_counts_per_ts'].values()
            if not counts:
                continue
            
            avg_vehicle_count = sum(counts) / len(counts)
            density_k = avg_vehicle_count / total_length_km

            all_speeds = values['speeds']
            speed_v_ms = np.average(all_speeds) if all_speeds else 0
            speed_v_kmh = speed_v_ms * 3.6

            flow_q = density_k * speed_v_kmh

            mfd_results[mesh_name]['K'].append(density_k)
            mfd_results[mesh_name]['Q'].append(flow_q)
            mfd_results[mesh_name]['time'].append(time_slot)
            
    return mfd_results

# 【新規追加】移動平均を適用する関数
def apply_moving_average(mfd_data):
    """
    MFDデータに15分（3点）の移動平均を適用する。
    """
    smoothed_mfd = defaultdict(lambda: {'K': [], 'Q': [], 'time': []})
    window_size = 3 # 15分 / 5分間隔 = 3点
    
    for mesh_name, data in mfd_data.items():
        if len(data['K']) < window_size:
            continue # データ点がウィンドウサイズより少ない場合はスキップ

        # pandas DataFrameを作成して時間でソート（calculate_mfdでソート済みだが念のため）
        df = pd.DataFrame(data).sort_values(by='time').reset_index(drop=True)
        
        # 15分（3点）の中心移動平均を計算
        df['K_ma'] = df['K'].rolling(window=window_size, center=True).mean()
        df['Q_ma'] = df['Q'].rolling(window=window_size, center=True).mean()
        
        # 移動平均が計算できないエッジ部分（NaN）を削除
        df.dropna(inplace=True)
        
        # 結果を新しい辞書に格納
        smoothed_mfd[mesh_name]['K'] = df['K_ma'].tolist()
        smoothed_mfd[mesh_name]['Q'] = df['Q_ma'].tolist()
        smoothed_mfd[mesh_name]['time'] = df['time'].tolist()
        
    return smoothed_mfd


def create_single_plot_base64(data, title, x_max, y_max):
    """MFDグラフの画像をBase64形式で生成する"""
    fig, ax = plt.subplots(figsize=(5, 4.5))
    
    if data and data['K']:
        hours = [t / 3600.0 for t in data['time']]
        scatter = ax.scatter(data['K'], data['Q'], c=hours, cmap='plasma', alpha=0.8, s=15)
        cbar = fig.colorbar(scatter, ax=ax)
        cbar.set_label('Time [hour]')
        
    ax.set_xlabel('Traffic Density (K) [vh/km]')
    ax.set_ylabel('Traffic Flow (Q) [vh/h]')
    ax.set_title(title)
    ax.set_xlim(0, x_max * 1.05 if x_max > 0 else 1)
    ax.set_ylim(0, y_max * 1.05 if y_max > 0 else 1)
    ax.grid(True, linestyle='--', alpha=0.6)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# --- 3. メイン処理 ---
def main():
    """メインの処理を実行する"""
    output_dir = os.path.dirname(OUTPUT_HTML)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"出力ディレクトリ '{output_dir}' を作成しました。")

    net_info = get_net_info(FILE_PATHS['net_step4'])
    utm_meshes = create_meshes(net_info['bounds'], MESH_ROWS, MESH_COLS)
    
    edge_lengths_step1 = calculate_total_edge_lengths(FILE_PATHS['net_step1'], utm_meshes)
    edge_lengths_step4 = calculate_total_edge_lengths(FILE_PATHS['net_step4'], utm_meshes)
    
    processed_step1 = process_fcd_file(FILE_PATHS['step1_fcd'], utm_meshes)
    processed_step4 = process_fcd_file(FILE_PATHS['step4_fcd'], utm_meshes)
    
    mfd_step1_raw = calculate_mfd(processed_step1, edge_lengths_step1)
    mfd_step4_raw = calculate_mfd(processed_step4, edge_lengths_step4)
    
    # 【変更】移動平均を適用
    print("MFDデータに15分移動平均を適用中...")
    mfd_step1 = apply_moving_average(mfd_step1_raw)
    mfd_step4 = apply_moving_average(mfd_step4_raw)
    print("移動平均の適用が完了しました。")

    lon_min, lat_min, lon_max, lat_max = net_info['orig_bounds']
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    
    lat_step = (lat_max - lat_min) / MESH_ROWS
    lon_step = (lon_max - lon_min) / MESH_COLS

    print("地図上にメッシュとグラフを作成中...")
    for mesh in utm_meshes:
        mesh_name = mesh['name']
        
        data1 = mfd_step1.get(mesh_name)
        data2 = mfd_step4.get(mesh_name)

        if not (data1 and data1['K']) and not (data2 and data2['K']):
            continue

        local_max_k = 0
        local_max_q = 0
        if data1 and data1['K']:
            local_max_k = max(local_max_k, max(data1['K']))
            local_max_q = max(local_max_q, max(data1['Q']))
        if data2 and data2['K']:
            local_max_k = max(local_max_k, max(data2['K']))
            local_max_q = max(local_max_q, max(data2['Q']))
        
        plot1_b64 = create_single_plot_base64(data1, "Step 1 (15min MA)", local_max_k, local_max_q)
        plot2_b64 = create_single_plot_base64(data2, "Step 4 (15min MA)", local_max_k, local_max_q)
        
        html = f'''
        <h4 style="text-align:center;">MFD: {mesh_name}</h4>
        <div style="display: flex; justify-content: space-around;">
            <div style="text-align:center;"><img src="data:image/png;base64,{plot1_b64}" width="320"></div>
            <div style="text-align:center;"><img src="data:image/png;base64,{plot2_b64}" width="320"></div>
        </div>'''
        popup = folium.Popup(html, max_width=700)
        
        i, j = mesh['row'], mesh['col']
        poly_lat_min = lat_min + (MESH_ROWS - 1 - i) * lat_step
        poly_lat_max = lat_min + (MESH_ROWS - i) * lat_step
        poly_lon_min = lon_min + j * lon_step
        poly_lon_max = lon_min + (j + 1) * lon_step
        
        points_latlon = [
            (poly_lat_min, poly_lon_min), (poly_lat_max, poly_lon_min),
            (poly_lat_max, poly_lon_max), (poly_lat_min, poly_lon_max)
        ]
        
        folium.Polygon(
            locations=points_latlon, popup=popup, tooltip=mesh_name,
            color='#E57200', fill=True, fill_opacity=0.2
        ).add_to(m)

    m.save(OUTPUT_HTML)
    print(f"処理が完了しました。結果は '{OUTPUT_HTML}' に保存されています。")

if __name__ == '__main__':
    main()