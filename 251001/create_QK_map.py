import xml.etree.ElementTree as ET
import pandas as pd
import folium
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import japanize_matplotlib
import os
import re
from collections import defaultdict
import base64
from io import BytesIO
from tqdm import tqdm

print("スクリプトを開始します。")

# --- 1. データ読み込みと解析のための補助関数 ---

def parse_edge_xml_to_coords(edg_xml_path):
    """SUMOのedge.xmlファイルを解析し、各エッジの中心座標を辞書として返す。"""
    print(f"'{edg_xml_path}' を解析しています...")
    try:
        tree = ET.parse(edg_xml_path)
    except FileNotFoundError:
        print(f"エラー: ファイル '{edg_xml_path}' が見つかりません。")
        return {}
    root = tree.getroot()
    edge_coords = {}
    for edge in tqdm(root.findall('edge'), desc=f"座標処理中 ({os.path.basename(edg_xml_path)})"):
        edge_id = edge.get('id')
        shape = edge.get('shape')
        if edge_id and shape:
            try:
                coords = [list(map(float, p.split(','))) for p in shape.split(' ')]
                # エッジの中心座標を計算 (単純な平均)
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                edge_coords[edge_id] = (avg_lat, avg_lon)
            except (ValueError, IndexError):
                continue
    return edge_coords

def parse_detector_xml(detector_xml_path):
    """detector.add.xmlファイルを解析し、detectorのprefixとedge_idをマッピングする。"""
    print(f"'{detector_xml_path}' を解析しています...")
    try:
        tree = ET.parse(detector_xml_path)
    except FileNotFoundError:
        print(f"エラー: ファイル '{detector_xml_path}' が見つかりません。")
        return {}
    root = tree.getroot()
    detector_to_edge = {}
    for detector in tqdm(root.findall('inductionLoop'), desc=f"Detector処理中 ({os.path.basename(detector_xml_path)})"):
        det_id = detector.get('id')
        lane_id = detector.get('lane')
        if det_id and lane_id:
            # detector IDからprefixを抽出 (QKplot.pyのロジックに合わせる)
            prefix = re.sub(r'_\d+_\d+$', '', det_id)
            # lane IDからedge IDを抽出
            edge_id = lane_id.split('_')[0]
            detector_to_edge[prefix] = edge_id
    return detector_to_edge

# --- 2. QKプロット生成関数 (QKplot.pyのロジックを内包) ---

def generate_qk_plot_image(df_grouped):
    """データフレームからQKプロットを生成し、画像データを返す。"""
    if df_grouped.empty:
        return None

    df_grouped["k"] = df_grouped["flow"] / df_grouped["vel"]
    df_grouped["hour"] = df_grouped["begin"] // 3600
    df_grouped = df_grouped[df_grouped["k"] > 0.01].copy()

    if df_grouped.empty:
        return None

    df_grouped["flow_ma"] = df_grouped["flow"].rolling(window=5, min_periods=1).mean()
    if df_grouped["flow_ma"].isna().all():
        return None

    # プロット作成
    fig, ax = plt.subplots(figsize=(6, 5))
    cmap = plt.colormaps['coolwarm']
    norm = mcolors.Normalize(vmin=0, vmax=23)
    
    scatter = ax.scatter(
        df_grouped["k"],
        df_grouped["flow_ma"],
        c=df_grouped["hour"],
        cmap=cmap,
        norm=norm,
        s=15,
        alpha=0.8
    )
    
    ax.set_xlabel("密度 K [台/km]")
    ax.set_ylabel("交通量 Q [台/h]")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.set_title(f"Q-K Plot")
    ax.grid(True, linestyle='--', alpha=0.6)

    cbar = plt.colorbar(scatter, ax=ax, ticks=range(0, 24, 3))
    cbar.set_label("時間帯")
    
    plt.tight_layout()
    
    # 画像をメモリ上のバッファに保存
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    # Base64エンコードして返す
    return base64.b64encode(buf.getvalue()).decode()

def process_output_xml(output_xml_path):
    """out.xmlを処理して、detector prefixごとのQKプロット画像を生成する。"""
    print(f"'{output_xml_path}' のシミュレーション結果を処理しています...")
    try:
        tree = ET.parse(output_xml_path)
    except FileNotFoundError:
        print(f"エラー: ファイル '{output_xml_path}' が見つかりません。")
        return {}
        
    root = tree.getroot()
    
    prefix_data = defaultdict(list)
    for data in tqdm(root.findall('interval'), desc=f"結果処理中 ({os.path.basename(output_xml_path)})"):
        prefix = re.sub(r'_\d+_\d+$', '', data.get('id'))
        prefix_data[prefix].append({
            'begin': float(data.get('begin')),
            'flow': float(data.get('flow')),
            'speed': float(data.get('speed', 0)) * 3.6  # m/s to km/h
        })

    plot_images = {}
    
    def weighted_harmonic_mean(df):
        velocities = df['speed']
        flows = df['flow']
        valid = (velocities > 0) & velocities.notna() & flows.notna()
        if not valid.any():
            return 0
        numerator = flows[valid].sum()
        denominator = (flows[valid] / velocities[valid]).sum()
        return numerator / denominator if denominator != 0 else 0

    for prefix, records in tqdm(prefix_data.items(), desc="QKプロット生成中"):
        df = pd.DataFrame(records)
        df_grouped = df.groupby("begin").agg(
            flow=('flow', 'sum'),
            vel=('speed', lambda x: weighted_harmonic_mean(df.loc[x.index]))
        ).reset_index()
        
        plot_images[prefix] = generate_qk_plot_image(df_grouped)
        
    return plot_images

# --- 3. メイン処理 ---

# ファイルパスの設定
files = {
    'step1': {
        'detector': '251001/data/detector_step1.add.xml',
        'edge': '250724/data/edge_step1.edg.xml',
        'out': '251001/data/out_1.xml'
    },
    'step2': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_2.xml'
    },
    'step3': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_3.xml'
    },
    'step4': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_4.xml'
    }
}

# 全ステップのデータを統合する辞書
# Structure: {edge_id: {'coords': (lat, lon), 'plots': {'step1': b64, ...}, 'prefixes': {'step1': prefix, ...}}}
edge_map_data = defaultdict(lambda: {'plots': {}, 'prefixes': {}})

# 各ステップのデータを処理
for step, paths in files.items():
    print(f"\n--- {step.upper()} の処理を開始 ---")
    det_to_edge = parse_detector_xml(paths['detector'])
    edge_coords = parse_edge_xml_to_coords(paths['edge'])
    qk_plots = process_output_xml(paths['out'])
    
    for prefix, edge_id in det_to_edge.items():
        if edge_id in edge_coords:
            edge_map_data[edge_id]['coords'] = edge_coords[edge_id]
            edge_map_data[edge_id]['prefixes'][step] = prefix
            if prefix in qk_plots and qk_plots[prefix]:
                edge_map_data[edge_id]['plots'][step] = qk_plots[prefix]

# --- 4. 地図の生成 ---
print("\n地図を生成しています...")

if not edge_map_data:
    print("エラー: 地図にプロットするデータがありません。ファイルパスや内容を確認してください。")
else:
    # 地図の中心を計算
    avg_lat = sum(v['coords'][0] for v in edge_map_data.values()) / len(edge_map_data)
    avg_lon = sum(v['coords'][1] for v in edge_map_data.values()) / len(edge_map_data)
    
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13, tiles='CartoDB positron')

    for edge_id, data in tqdm(edge_map_data.items(), desc="マーカーを配置中"):
        if 'coords' not in data:
            continue

        # ポップアップ用のHTMLを作成
        html_content = f"<h4>Edge ID: {edge_id}</h4>"

        # Flexboxを使用してプロットを横一列に並べる
        # flex-wrap: nowrap; で折り返しを禁止し、overflow-x: auto; で横スクロールを可能にする
        html_content += '<div style="display: flex; flex-direction: row; flex-wrap: nowrap; overflow-x: auto; gap: 15px; padding: 10px;">'

        has_plot = False
        for step_num in range(1, 5):
            step = f'step{step_num}'
            if step in data['plots']:
                has_plot = True
                prefix = data['prefixes'].get(step, "N/A")
                b64_img = data['plots'][step]
                
                html_content += f"""
                <div style="text-align: center; margin: 5px;">
                    <b>{step.upper()}</b><br>
                    <small>Detector: {prefix}</small><br>
                    <img src="data:image/png;base64,{b64_img}" width="350">
                </div>
                """
        html_content += '</div>'
        
        if not has_plot:
            html_content += "<p>表示できるQKプロットがありませんでした。</p>"

        popup = folium.Popup(html_content, max_width=1500)
        
        folium.CircleMarker(
            location=data['coords'],
            radius=6,
            popup=popup,
            color='#3186cc',
            fill=True,
            fill_color='#3186cc',
            fill_opacity=0.7
        ).add_to(m)

    # 地図をHTMLファイルとして保存
    output_filename = "251001/data/qk_simulation_map.html"
    m.save(output_filename)
    print(f"\n処理が完了しました。'{output_filename}' をブラウザで開いてください。")