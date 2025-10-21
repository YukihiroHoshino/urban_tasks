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
import numpy as np

print("スクリプトを開始します。")

# --- 1. データ読み込みと解析のための補助関数 (変更なし) ---

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
            prefix = re.sub(r'_\d+_\d+$', '', det_id)
            edge_id = lane_id.split('_')[0]
            detector_to_edge[prefix] = edge_id
    return detector_to_edge

# --- 2. QKプロット生成関数の修正 ---

# ▼▼▼ 修正箇所 ▼▼▼
# 共通の軸の最大値を引数として受け取るように関数を修正
def generate_qk_plot_image(df_grouped, xlim_max, ylim_max):
    """データフレームからQKプロットを生成し、画像データを返す。"""
    if df_grouped.empty or df_grouped["flow_ma"].isna().all():
        return None

    # プロット作成
    fig, ax = plt.subplots(figsize=(6, 5))
    cmap = plt.colormaps['hsv']
    
    scatter = ax.scatter(
        df_grouped["k"],
        df_grouped["flow_ma"],
        c=df_grouped["hour"],
        cmap=cmap,
        s=15,
        alpha=0.8,
        vmin=0,
        vmax=24
    )
    
    ax.set_xlabel("密度 K [台/km]", fontsize=15)
    ax.set_ylabel("交通量 Q [台/h]", fontsize=15)
    # 共通の最大値を軸に設定
    ax.set_xlim(0, xlim_max)
    ax.set_ylim(0, ylim_max)
    ax.set_title(f"Q-K Plot")
    ax.grid(True, linestyle='--', alpha=0.6)

    cbar = plt.colorbar(scatter, ax=ax, ticks=range(0, 24, 3))
    cbar.set_label("時間帯")
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    return base64.b64encode(buf.getvalue()).decode()

# ▼▼▼ 修正箇所 ▼▼▼
# グラフ描画は行わず、計算済みのDataFrameを返すように変更
def process_output_to_dataframes(output_xml_path):
    """out.xmlを処理し、detector prefixごとのDataFrameを返す。"""
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
            'speed': float(data.get('speed', 0)) * 3.6
        })

    dataframes = {}
    
    def weighted_harmonic_mean(df):
        velocities = df['speed']
        flows = df['flow']
        valid = (velocities > 0) & velocities.notna() & flows.notna()
        if not valid.any(): return 0
        numerator = flows[valid].sum()
        denominator = (flows[valid] / velocities[valid]).sum()
        return numerator / denominator if denominator != 0 else 0

    for prefix, records in tqdm(prefix_data.items(), desc="データフレーム生成中"):
        df = pd.DataFrame(records)
        df_grouped = df.groupby("begin").agg(
            flow=('flow', 'sum'),
            vel=('speed', lambda x: weighted_harmonic_mean(df.loc[x.index]))
        ).reset_index()
        
        # QKプロットに必要な列を計算
        df_grouped["k"] = df_grouped["flow"] / df_grouped["vel"].replace(0, np.nan)
        df_grouped["hour"] = df_grouped["begin"] // 3600

        # 無効値除外
        df_grouped = df_grouped[
            (df_grouped["k"] > 0.01) & 
            (df_grouped["hour"] >= 0) & 
            (df_grouped["hour"] < 24)
        ].copy()
        
        if df_grouped.empty: continue
        df_grouped["flow_ma"] = df_grouped["flow"].rolling(window=5, min_periods=1).mean()
        dataframes[prefix] = df_grouped
        
    return dataframes
# ▲▲▲ 修正箇所 ▲▲▲

# --- 3. メイン処理 ---

# ファイルパスの設定 (ご自身の環境に合わせて修正してください)
files = {
    'step1': {
        'detector': '251001/data/detector_step1.add.xml',
        'edge': '250724/data/edge_step1.edg.xml',
        'out': '251001/data/out_thursday_step1.xml'
    },
    'step2': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_thursday_step2.xml'
    },
    'step3': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_thursday_step3.xml'
    },
    'step4': {
        'detector': '251001/data/detector_IC.add.xml',
        'edge': '250724/data/edge_IC.edg.xml',
        'out': '251001/data/out_thursday_step4.xml'
    }
}


# ▼▼▼ 修正箇所 ▼▼▼
# データ構造を変更: plotsの代わりにdataframesを格納
edge_map_data = defaultdict(lambda: {'dataframes': {}, 'prefixes': {}})

# ステップ1: 全ステップのデータを読み込み、DataFrameとして格納
for step, paths in files.items():
    print(f"\n--- {step.upper()} のデータ処理を開始 ---")
    det_to_edge = parse_detector_xml(paths['detector'])
    edge_coords = parse_edge_xml_to_coords(paths['edge'])
    qk_dataframes = process_output_to_dataframes(paths['out'])
    
    for prefix, edge_id in det_to_edge.items():
        if edge_id in edge_coords and prefix in qk_dataframes:
            edge_map_data[edge_id]['coords'] = edge_coords[edge_id]
            edge_map_data[edge_id]['prefixes'][step] = prefix
            edge_map_data[edge_id]['dataframes'][step] = qk_dataframes[prefix]

# ステップ2: 各エッジで軸の最大値を計算し、共通スケールでプロットを生成
print("\n--- 全てのプロットを共通スケールで再生成 ---")
for edge_id, data in tqdm(edge_map_data.items(), desc="共通スケールでプロット生成中"):
    all_dfs = list(data['dataframes'].values())
    if not all_dfs: continue

    # エッジ内の全ステップを通じてkとflow_maの最大値を取得
    max_k = 0
    max_flow = 0
    for df in all_dfs:
        if not df.empty:
            max_k = max(max_k, df['k'].max())
            max_flow = max(max_flow, df['flow_ma'].max())
    
    # 軸に見やすさのためのマージンを追加
    plot_xlim = max_k * 1.05
    plot_ylim = max_flow * 1.05
    
    # プロットを格納する新しい辞書を作成
    data['plots'] = {}
    
    # 計算した最大値を使って、各ステップのプロットを生成
    for step, df in data['dataframes'].items():
        b64_img = generate_qk_plot_image(df, plot_xlim, plot_ylim)
        if b64_img:
            data['plots'][step] = b64_img
# ▲▲▲ 修正箇所 ▲▲▲


# --- 4. 地図の生成 ---
print("\n地図を生成しています...")

if not edge_map_data:
    print("エラー: 地図にプロットするデータがありません。ファイルパスや内容を確認してください。")
else:
    avg_lat = sum(v['coords'][0] for v in edge_map_data.values() if 'coords' in v) / len(edge_map_data)
    avg_lon = sum(v['coords'][1] for v in edge_map_data.values() if 'coords' in v) / len(edge_map_data)
    
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13, tiles='CartoDB positron')

    for edge_id, data in tqdm(edge_map_data.items(), desc="マーカーを配置中"):
        if 'coords' not in data: continue

        html_content = f"<h4>Edge ID: {edge_id}</h4>"
        html_content += '<div style="display: flex; flex-direction: row; flex-wrap: nowrap; overflow-x: auto; gap: 15px; padding: 10px;">'
        
        has_plot = False
        # 'plots'キーに格納された画像データを使用
        if 'plots' in data:
            for step_num in range(1, 5):
                step = f'step{step_num}'
                if step in data['plots']:
                    has_plot = True
                    prefix = data['prefixes'].get(step, "N/A")
                    b64_img = data['plots'][step]
                    
                    html_content += f"""
                    <div style="text-align: center; flex-shrink: 0;">
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

    output_filename = "251001/data/qk_map_scaled_thursday.html"
    m.save(output_filename)
    print(f"\n処理が完了しました。'{output_filename}' をブラウザで開いてください。")