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
import json
import japanize_matplotlib

# --- 1. 設定項目 ---
FILE_PATHS = {
    'net_step1': '251027/data/master_forResearch_fixed_bukai_step1_truck_jp_parking.net.xml',
    'net_step4': '251027/data/master_forResearch_fixed_bukai_step4_truck_jp_parking.net.xml',
    'step1_fcd': '251027/data/sunday_step1_edit_fcd.xml',
    'step4_fcd': '251027/data/sunday_step4_edit_fcd.xml'
}
OUTPUT_HTML = '251027/fig/map_with_sidebar_fixed1104.html'

# 計算設定
MESH_ROWS = 18
MESH_COLS = 15
TIME_INTERVAL = 300
MOVING_AVG_WINDOW = 1
SPEED_THRESHOLD_KMH = 20
TIME_RANGE_MIN = 6 * 3600
TIME_RANGE_MAX = 20 * 3600
CHANGE_THRESHOLD = 5

# --- 2. 補助関数 (変更なし) ---
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

def process_fcd_file_detailed(fcd_file, meshes):
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
                            data[mesh_name][time_slot]['speeds'].append(speed_ms)
                            data[mesh_name][time_slot]['vehicle_counts_per_ts'][time] += 1
                elem.clear()
    except ET.ParseError as e:
        warnings.warn(f"警告: '{fcd_file}' 解析中にエラー: {e}")
    print(f"'{fcd_file}' の詳細処理が完了しました。")
    return data

def calculate_average_speeds(processed_data):
    avg_speeds = defaultdict(dict)
    for mesh_name, time_slots in processed_data.items():
        times, speeds_kmh = [], []
        for time in sorted(time_slots.keys()):
            times.append(time)
            avg_speed = np.mean(time_slots[time]['speeds']) * 3.6 if time_slots[time]['speeds'] else np.nan
            speeds_kmh.append(avg_speed)
        avg_speeds[mesh_name] = {'time': times, 'avg_speed_kmh': speeds_kmh}
    return avg_speeds

def count_low_speed_events(speed_data):
    if not speed_data or not speed_data.get('time'): return 0
    df = pd.DataFrame(speed_data).sort_values(by='time').reset_index(drop=True)
    df['avg_speed_kmh'] = df['avg_speed_kmh'].interpolate(method='linear')
    df['speed_ma'] = df['avg_speed_kmh'].rolling(window=MOVING_AVG_WINDOW, center=True).mean()
    return int((df['speed_ma'] <= SPEED_THRESHOLD_KMH).sum())

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
                if mesh_name: mesh_lengths[mesh_name] += length_m
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
        cbar = fig.colorbar(scatter, ax=ax); cbar.set_label('Time [hour]')
    ax.set_xlabel('Traffic Density (K) [vh/km]'); ax.set_ylabel('Traffic Flow (Q) [vh/h]')
    ax.set_title(title); ax.set_xlim(0, x_max * 1.05 if x_max > 0 else 1)
    ax.set_ylim(0, y_max * 1.05 if y_max > 0 else 1); ax.grid(True, linestyle='--', alpha=0.6)
    buf = io.BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# --- 3. メイン処理 ---
def main():
    output_dir = os.path.dirname(OUTPUT_HTML)
    if output_dir and not os.path.exists(output_dir): os.makedirs(output_dir)
    net_info = get_net_info(FILE_PATHS['net_step4'])
    utm_meshes = create_meshes(net_info['bounds'], MESH_ROWS, MESH_COLS)
    processed_detailed_s1 = process_fcd_file_detailed(FILE_PATHS['step1_fcd'], utm_meshes)
    processed_detailed_s4 = process_fcd_file_detailed(FILE_PATHS['step4_fcd'], utm_meshes)
    avg_speeds_s1 = calculate_average_speeds(processed_detailed_s1)
    avg_speeds_s4 = calculate_average_speeds(processed_detailed_s4)
    edge_lengths_s1 = calculate_total_edge_lengths(FILE_PATHS['net_step1'], utm_meshes)
    edge_lengths_s4 = calculate_total_edge_lengths(FILE_PATHS['net_step4'], utm_meshes)
    mfd_s1_raw = calculate_mfd(processed_detailed_s1, edge_lengths_s1)
    mfd_s4_raw = calculate_mfd(processed_detailed_s4, edge_lengths_s4)
    mfd_s1 = apply_moving_average_mfd(mfd_s1_raw)
    mfd_s4 = apply_moving_average_mfd(mfd_s4_raw)

    lon_min, lat_min, lon_max, lat_max = net_info['orig_bounds']
    center_lat, center_lon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')
    
    cmap = plt.get_cmap('coolwarm', 5)
    color_map = {
        '大幅改善': colors.to_hex(cmap(0.0)), 'やや改善': colors.to_hex(cmap(0.25)),
        '変化なし': '#BEBEBE', 'やや悪化': colors.to_hex(cmap(0.75)),
        '大幅悪化': colors.to_hex(cmap(1.0))
    }
    
    all_mesh_data = {}
    print("全メッシュのデータを生成中...")
    for mesh in utm_meshes:
        mesh_name = mesh['name']
        if mesh_name not in avg_speeds_s1 and mesh_name not in avg_speeds_s4: continue
        
        count1 = count_low_speed_events(avg_speeds_s1.get(mesh_name, {}))
        count4 = count_low_speed_events(avg_speeds_s4.get(mesh_name, {}))
        diff = count1 - count4
        if diff > CHANGE_THRESHOLD: status = '大幅改善'
        elif 0 < diff <= CHANGE_THRESHOLD: status = 'やや改善'
        elif diff == 0: status = '変化なし'
        elif -CHANGE_THRESHOLD <= diff < 0: status = 'やや悪化'
        else: status = '大幅悪化'
        
        data1_mfd = mfd_s1.get(mesh_name)
        data2_mfd = mfd_s4.get(mesh_name)
        plot1_b64, plot2_b64 = "", ""
        if (data1_mfd and data1_mfd.get('K')) or (data2_mfd and data2_mfd.get('K')):
            local_max_k = max(data1_mfd.get('K', [0])) if data1_mfd else 0
            local_max_q = max(data1_mfd.get('Q', [0])) if data1_mfd else 0
            if data2_mfd:
                local_max_k = max(local_max_k, max(data2_mfd.get('K', [0])))
                local_max_q = max(local_max_q, max(data2_mfd.get('Q', [0])))
            plot1_b64 = create_single_plot_base64(data1_mfd, "QK Plot: Step 1", local_max_k, local_max_q)
            plot2_b64 = create_single_plot_base64(data2_mfd, "QK Plot: Step 4", local_max_k, local_max_q)

        all_mesh_data[mesh_name] = {
            "status": status, "count1": count1, "count4": count4, "diff": diff,
            "plot1": plot1_b64, "plot2": plot2_b64
        }
        
        color = color_map[status]
        fill_opacity = 0.3 if status == '変化なし' else 0.5
        i, j = mesh['row'], mesh['col']
        lat_step, lon_step = (lat_max - lat_min) / MESH_ROWS, (lon_max - lon_min) / MESH_COLS
        poly_lat_min, poly_lat_max = lat_min + (MESH_ROWS - 1 - i) * lat_step, lat_min + (MESH_ROWS - i) * lat_step
        poly_lon_min, poly_lon_max = lon_min + j * lon_step, lon_min + (j + 1) * lon_step
        points = [(poly_lat_min, poly_lon_min), (poly_lat_max, poly_lon_min),
                  (poly_lat_max, poly_lon_max), (poly_lat_min, poly_lon_max)]
        
        p = folium.Polygon(
            locations=points, tooltip=f"{mesh_name} | {status} ({count1}→{count4})",
            weight=0, fill=True, fill_color=color, fill_opacity=fill_opacity
        )
        p.add_to(m)
        m.get_root().html.add_child(folium.Element(f"<script>document.body.lastChild.setAttribute('mesh-id', '{mesh_name}');</script>"))

    js_data_string = json.dumps(all_mesh_data)

    # ★★★ ここからが修正箇所 ★★★
    # 簡略化されたHTML/CSS/JSブロック
    html_css_js = f"""
    <style>
        body {{ 
            display: flex; 
            margin: 0; /* bodyのデフォルトマージンをリセット */
        }}
        .folium-map {{
            flex-grow: 1; /* 地図が残りのスペースを埋めるように */
            height: 100vh !important; /* 高さを画面全体に */
        }}
        #sidebar {{
            width: 33%; max-width: 500px; min-width: 400px;
            height: 100vh; overflow-y: auto; z-index: 1000;
            background-color: #f9f9f9; border-left: 2px solid #ccc;
            padding: 15px; box-sizing: border-box; font-family: sans-serif;
        }}
        #sidebar h2 {{ margin-top: 0; }}
        #sidebar h3 {{ margin-top: 10px; }}
        #sidebar h4 {{ text-align: center; margin-bottom: 5px; }}
        #sidebar .plot-container {{ display: flex; justify-content: space-around; }}
        #sidebar .plot-container img {{ max-width: 48%; height: auto; }}
        #sidebar .placeholder {{ color: #777; text-align: center; margin-top: 50px; }}
        .leaflet-container {{ cursor: pointer !important; }}
    </style>

    <div id="sidebar">
        <h2>メッシュ情報</h2>
        <div id="sidebar-content">
            <p class="placeholder">地図上のメッシュをクリックして詳細を表示</p>
        </div>
    </div>

    <script>
        const allData = {js_data_string};

        function updateSidebar(meshId) {{
            const data = allData[meshId];
            if (!data) return;

            const contentDiv = document.getElementById('sidebar-content');
            
            let qk_plot_html = '';
            if (data.plot1 || data.plot2) {{
                qk_plot_html = `
                    <hr><h4>QK Plot (15min MA)</h4>
                    <div class="plot-container">
                        <div><img src="data:image/png;base64,${{data.plot1}}"></div>
                        <div><img src="data:image/png;base64,${{data.plot2}}"></div>
                    </div>
                `;
            }}

            contentDiv.innerHTML = `
                <h3><b>メッシュ: ${{meshId}}</b> (${{data.status}})</h3>
                <hr>
                <p>時速{SPEED_THRESHOLD_KMH}km以下の回数:</p>
                <ul>
                    <li><b>Step1 (整備前):</b> ${{data.count1}} 回</li>
                    <li><b>Step4 (整備後):</b> ${{data.count4}} 回</li>
                    <li><b>改善度 (差):</b> ${{data.diff}} 回</li>
                </ul>
                ${{qk_plot_html}}
            `;
        }}

        // DOMの準備完了後にイベントリスナーを設定
        document.addEventListener("DOMContentLoaded", function() {{
            const mapDiv = document.querySelector('.folium-map');
            
            // サイドバーを地図の隣に配置
            document.body.appendChild(document.getElementById('sidebar'));

            mapDiv.addEventListener('click', function(e) {{
                let target = e.target;
                while (target && target.tagName !== 'path' && target.parentElement) {{
                    target = target.parentElement;
                }}
                if (target && target.getAttribute('mesh-id')) {{
                    const meshId = target.getAttribute('mesh-id');
                    updateSidebar(meshId);
                }}
            }});
        }});
    </script>
    """

    # 以前のコンテナ作成行は不要
    # m.get_root().html.add_child(folium.Element(f'<div id="map-container"></div>'))
    m.get_root().html.add_child(folium.Element(html_css_js))
    
    legend_html = '''
    <div style="position: fixed; bottom: 20px; left: 20px; width: 150px; 
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