import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as colors
import folium
import io
import base64
import os
import warnings
from collections import defaultdict
import japanize_matplotlib

# --- 1. 設定項目 ---
FILE_PATHS = {
    # net_step1は道路延長計算のために追加
    'net_step1': '251027/data/master_forResearch_fixed_bukai_step1_truck_jp_parking.net.xml',
    'net_step4': '251027/data/master_forResearch_fixed_bukai_step4_truck_jp_parking.net.xml',
    'step1_fcd': '251027/data/sunday_step1_edit_fcd.xml',
    'step4_fcd': '251027/data/sunday_step4_edit_fcd.xml'
}
OUTPUT_HTML = '251027/fig/congestion_and_mfd_map1104_1by1_2_24h.html'

# 計算設定
MESH_ROWS = 1
MESH_COLS = 1
TIME_INTERVAL = 300
MOVING_AVG_WINDOW = 1
SPEED_THRESHOLD_KMH = 20
TIME_RANGE_MIN = 0 * 3600
TIME_RANGE_MAX = 24 * 3600
CHANGE_THRESHOLD = 5

# --- 2. 補助関数 ---

def get_net_info(net_file):
    print(f"'{net_file}' を解析中...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    location = root.find('location')
    conv_boundary = [float(x) for x in location.attrib['convBoundary'].split(',')]
    orig_boundary = [float(x) for x in location.attrib['origBoundary'].split(',')]
    return {'bounds': tuple(conv_boundary), 'orig_bounds': tuple(orig_boundary)}

def create_meshes(bounds, rows, cols):
    min_x, min_y, max_x, max_y = bounds
    mesh_width = (max_x - min_x) / cols
    mesh_height = (max_y - min_y) / rows
    meshes = []
    for i in range(rows):
        for j in range(cols):
            # メッシュ名を比較元コードと合わせる
            mesh_name = f"mesh_{rows-i}_{j+1}"
            m_min_y = min_y + i * mesh_height
            m_max_y = min_y + (i + 1) * mesh_height
            m_min_x = min_x + j * mesh_width
            m_max_x = min_x + (j + 1) * mesh_width
            meshes.append({'name': mesh_name, 'bounds': (m_min_x, m_min_y, m_max_x, m_max_y), 'row': rows - 1 - i, 'col': j})
    print(f"{rows}x{cols} のメッシュを作成しました。")
    return meshes

def get_mesh_for_coord(x, y, meshes):
    for mesh in meshes:
        min_x, min_y, max_x, max_y = mesh['bounds']
        if min_x <= x < max_x and min_y <= y < max_y:
            return mesh['name']
    return None

# 【更新】QKプロット計算のため、詳細な情報を集計するバージョンに変更
def process_fcd_file_detailed(fcd_file, meshes):
    """FCDファイルを解析し、速度と車両数を集計する（QKプロット用）"""
    print(f"'{fcd_file}' を詳細に処理中...")
    data = defaultdict(lambda: defaultdict(lambda: {'speeds': [], 'vehicle_counts_per_ts': defaultdict(int)}))
    try:
        context = ET.iterparse(fcd_file, events=('end',))
        for _, elem in context:
            if elem.tag == 'timestep':
                time = float(elem.attrib['time'])
                if not (TIME_RANGE_MIN <= time < TIME_RANGE_MAX):
                    elem.clear()
                    continue
                time_slot = int(time / TIME_INTERVAL) * TIME_INTERVAL
                for vehicle in elem:
                    if vehicle.tag == 'vehicle':
                        x, y = float(vehicle.attrib['x']), float(vehicle.attrib['y'])
                        mesh_name = get_mesh_for_coord(x, y, meshes)
                        if mesh_name:
                            speed_ms = float(vehicle.attrib['speed'])
                            data[mesh_name][time_slot]['speeds'].append(speed_ms) # m/sで保持
                            data[mesh_name][time_slot]['vehicle_counts_per_ts'][time] += 1
                elem.clear()
    except ET.ParseError as e:
        warnings.warn(f"警告: '{fcd_file}' 解析中にエラー: {e}")
    print(f"'{fcd_file}' の詳細処理が完了しました。")
    return data

# 【更新】新しいデータ構造に合わせて修正
def calculate_average_speeds(processed_data):
    """メッシュ・時間帯ごとの平均速度を計算する"""
    avg_speeds = defaultdict(dict)
    for mesh_name, time_slots in processed_data.items():
        times, speeds_kmh = [], []
        for time in sorted(time_slots.keys()):
            times.append(time)
            # speedsはm/sなのでkm/hに変換
            avg_speed = np.mean(time_slots[time]['speeds']) * 3.6 if time_slots[time]['speeds'] else np.nan
            speeds_kmh.append(avg_speed)
        avg_speeds[mesh_name] = {'time': times, 'avg_speed_kmh': speeds_kmh}
    return avg_speeds

def count_low_speed_events(speed_data):
    if not speed_data or not speed_data.get('time'):
        return 0
    df = pd.DataFrame(speed_data).sort_values(by='time').reset_index(drop=True)
    df['avg_speed_kmh'] = df['avg_speed_kmh'].interpolate(method='linear')
    df['speed_ma'] = df['avg_speed_kmh'].rolling(window=MOVING_AVG_WINDOW, center=True).mean()
    return int((df['speed_ma'] <= SPEED_THRESHOLD_KMH).sum())

# --- QKプロット用の関数群 (参照コードから追加) ---

def calculate_total_edge_lengths(net_file, meshes):
    print(f"'{net_file}' から道路延長を計算中...")
    tree = ET.parse(net_file)
    root = tree.getroot()
    mesh_lengths = defaultdict(float)
    for edge in root.findall('edge'):
        if 'shape' in edge.attrib:
            points = [tuple(map(float, p.split(','))) for p in edge.attrib['shape'].split(' ')]
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i+1]
                mid_x, mid_y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                length_m = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                mesh_name = get_mesh_for_coord(mid_x, mid_y, meshes)
                if mesh_name:
                    mesh_lengths[mesh_name] += length_m
    return {name: length / 1000.0 for name, length in mesh_lengths.items()}

def calculate_mfd(processed_data, mesh_edge_lengths):
    mfd_results = defaultdict(lambda: {'K': [], 'Q': [], 'time': []})
    for mesh_name, time_slots in processed_data.items():
        total_length_km = mesh_edge_lengths.get(mesh_name, 0)
        if total_length_km == 0: continue
        for time_slot, values in sorted(time_slots.items()):
            counts = values['vehicle_counts_per_ts'].values()
            if not counts: continue
            avg_vehicle_count = sum(counts) / len(counts)
            density_k = avg_vehicle_count / total_length_km
            speed_v_ms = np.average(values['speeds']) if values['speeds'] else 0
            flow_q = density_k * (speed_v_ms * 3.6)
            mfd_results[mesh_name]['K'].append(density_k)
            mfd_results[mesh_name]['Q'].append(flow_q)
            mfd_results[mesh_name]['time'].append(time_slot)
    return mfd_results

def apply_moving_average_mfd(mfd_data):
    smoothed_mfd = defaultdict(lambda: {'K': [], 'Q': [], 'time': []})
    for mesh_name, data in mfd_data.items():
        if len(data['K']) < MOVING_AVG_WINDOW: continue
        df = pd.DataFrame(data).sort_values(by='time').reset_index(drop=True)
        df['K_ma'] = df['K'].rolling(window=MOVING_AVG_WINDOW, center=True).mean()
        df['Q_ma'] = df['Q'].rolling(window=MOVING_AVG_WINDOW, center=True).mean()
        df.dropna(inplace=True)
        smoothed_mfd[mesh_name]['K'] = df['K_ma'].tolist()
        smoothed_mfd[mesh_name]['Q'] = df['Q_ma'].tolist()
        smoothed_mfd[mesh_name]['time'] = df['time'].tolist()
    return smoothed_mfd

def create_single_plot_base64(data, title, x_max, y_max):
    fig, ax = plt.subplots(figsize=(5, 4.5))
    if data and data.get('K'):
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
    output_dir = os.path.dirname(OUTPUT_HTML)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    net_info = get_net_info(FILE_PATHS['net_step4'])
    utm_meshes = create_meshes(net_info['bounds'], MESH_ROWS, MESH_COLS)
    
    # --- データ処理 ---
    # 1. QKプロットと渋滞カウントの両方に使う詳細データを読み込む
    processed_detailed_s1 = process_fcd_file_detailed(FILE_PATHS['step1_fcd'], utm_meshes)
    processed_detailed_s4 = process_fcd_file_detailed(FILE_PATHS['step4_fcd'], utm_meshes)

    # 2. 渋滞カウント用の平均速度を計算
    avg_speeds_s1 = calculate_average_speeds(processed_detailed_s1)
    avg_speeds_s4 = calculate_average_speeds(processed_detailed_s4)
    
    # 3. QKプロット用のデータを計算
    print("QKプロット用のデータを計算中...")
    edge_lengths_s1 = calculate_total_edge_lengths(FILE_PATHS['net_step1'], utm_meshes)
    edge_lengths_s4 = calculate_total_edge_lengths(FILE_PATHS['net_step4'], utm_meshes)
    mfd_s1_raw = calculate_mfd(processed_detailed_s1, edge_lengths_s1)
    mfd_s4_raw = calculate_mfd(processed_detailed_s4, edge_lengths_s4)
    mfd_s1 = apply_moving_average_mfd(mfd_s1_raw)
    mfd_s4 = apply_moving_average_mfd(mfd_s4_raw)
    print("QKプロット用データの計算が完了しました。")

    # --- 地図作成 ---
    lon_min, lat_min, lon_max, lat_max = net_info['orig_bounds']
    center_lat, center_lon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')
    lat_step, lon_step = (lat_max - lat_min) / MESH_ROWS, (lon_max - lon_min) / MESH_COLS

    cmap = plt.get_cmap('coolwarm', 5)
    color_map = {
        '大幅改善': colors.to_hex(cmap(0.0)), 'やや改善': colors.to_hex(cmap(0.25)),
        '変化なし': '#BEBEBE', 'やや悪化': colors.to_hex(cmap(0.75)),
        '大幅悪化': colors.to_hex(cmap(1.0))
    }

    print("地図上にメッシュを描画中...")
    for mesh in utm_meshes:
        mesh_name = mesh['name']
        
        if mesh_name not in avg_speeds_s1 and mesh_name not in avg_speeds_s4:
            continue
        
        # 渋滞カウントとステータス判定
        count1 = count_low_speed_events(avg_speeds_s1.get(mesh_name, {}))
        count4 = count_low_speed_events(avg_speeds_s4.get(mesh_name, {}))
        diff = count1 - count4
        if diff > CHANGE_THRESHOLD: status = '大幅改善'
        elif 0 < diff <= CHANGE_THRESHOLD: status = 'やや改善'
        elif diff == 0: status = '変化なし'
        elif -CHANGE_THRESHOLD <= diff < 0: status = 'やや悪化'
        else: status = '大幅悪化'
        
        color = color_map[status]
        fill_opacity = 0.3 if status == '変化なし' else 0.5

        # --- ポップアップHTML作成 ---
        # 1. 渋滞カウント情報
        popup_html = f"""
        <b>メッシュ: {mesh_name}</b> ({status})<br><hr>
        時速{SPEED_THRESHOLD_KMH}km以下の回数 (15分移動平均後):<br>
        - <b>Step1 (整備前):</b> {count1} 回<br>
        - <b>Step4 (整備後):</b> {count4} 回<br>
        - <b>改善度 (差):</b> {diff} 回
        """

        # 2. QKプロット情報
        data1_mfd = mfd_s1.get(mesh_name)
        data2_mfd = mfd_s4.get(mesh_name)
        
        if (data1_mfd and data1_mfd['K']) or (data2_mfd and data2_mfd['K']):
            local_max_k = max(data1_mfd.get('K', [0])) if data1_mfd else 0
            local_max_q = max(data1_mfd.get('Q', [0])) if data1_mfd else 0
            if data2_mfd:
                local_max_k = max(local_max_k, max(data2_mfd.get('K', [0])))
                local_max_q = max(local_max_q, max(data2_mfd.get('Q', [0])))
            
            plot1_b64 = create_single_plot_base64(data1_mfd, "QK Plot: Step 1", local_max_k, local_max_q)
            plot2_b64 = create_single_plot_base64(data2_mfd, "QK Plot: Step 4", local_max_k, local_max_q)
            
            popup_html += f'''
            <hr><h4 style="text-align:center; margin-bottom:5px;">QK Plot (15min MA)</h4>
            <div style="display: flex; justify-content: space-around;">
                <div style="text-align:center;"><img src="data:image/png;base64,{plot1_b64}" width="320"></div>
                <div style="text-align:center;"><img src="data:image/png;base64,{plot2_b64}" width="320"></div>
            </div>'''
        
        popup = folium.Popup(popup_html, max_width=700)
        
        i, j = mesh['row'], mesh['col']
        poly_lat_min = lat_min + (MESH_ROWS - 1 - i) * lat_step
        poly_lat_max = lat_min + (MESH_ROWS - i) * lat_step
        poly_lon_min = lon_min + j * lon_step
        poly_lon_max = lon_min + (j + 1) * lon_step
        points_latlon = [(poly_lat_min, poly_lon_min), (poly_lat_max, poly_lon_min),
                         (poly_lat_max, poly_lon_max), (poly_lat_min, poly_lon_max)]
        
        folium.Polygon(
            locations=points_latlon, popup=popup, tooltip=f"{mesh_name} | {status} ({count1}→{count4})",
            weight=0, fill=True, fill_color=color, fill_opacity=fill_opacity
        ).add_to(m)

    # 凡例を追加
    legend_html = '''
    <div style="position: fixed; bottom: 50px; right: 50px; width: 150px; height: 130px; 
                border:2px solid grey; z-index:9999; font-size:14px; background-color:white;">
      &nbsp; <b>凡例</b><br>
      &nbsp; <i class="fa fa-square" style="color:{大幅改善}"></i>&nbsp; 大幅改善<br>
      &nbsp; <i class="fa fa-square" style="color:{やや改善}"></i>&nbsp; やや改善<br>
      &nbsp; <i class="fa fa-square" style="color:{変化なし}"></i>&nbsp; 変化なし<br>
      &nbsp; <i class="fa fa-square" style="color:{やや悪化}"></i>&nbsp; やや悪化<br>
      &nbsp; <i class="fa fa-square" style="color:{大幅悪化}"></i>&nbsp; 大幅悪化<br>
    </div>'''.format(**color_map)
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(OUTPUT_HTML)
    print(f"処理が完了しました。結果は '{OUTPUT_HTML}' に保存されています。")

if __name__ == '__main__':
    main()