import pandas as pd
import folium
# from folium.plugins import MarkerCluster # MarkerClusterは不要なため削除

# --- 1. データの読み込みと準備 ---

csv_file = '250930/data/tripinfo_with_coords_4.csv'
print(f"'{csv_file}' を読み込んでいます...")
df = pd.read_csv(csv_file)

# 緯度経度が欠損している行を削除
original_count = len(df)
df.dropna(subset=['depart_lon', 'depart_lat'], inplace=True)
print(f"座標が欠損していた {original_count - len(df)} 件のデータを除外しました。")

# TimeLossの差を計算
df['timeloss_diff'] = df['step4_timeLoss'] - df['step1_timeLoss']

# 差の正負に応じて色を決定する関数
def assign_color(diff):
    if diff > 0:
        return 'red'    # 悪化
    elif diff < 0:
        return 'blue'   # 改善
    else:
        return 'green'  # 変化なし

df['color'] = df['timeloss_diff'].apply(assign_color)

# --- 2. ベースマップの作成 ---

# 地図の中心をデータの平均座標に設定
center_lat = df['depart_lat'].mean()
center_lon = df['depart_lon'].mean()

# Foliumマップオブジェクトを作成
m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')

print("地図上にマーカーをプロットしています...")
# MarkerClusterの行は削除


# --- 3. マーカーのプロット ---

# データフレームの各行をループして、地図にマーカーを追加
for idx, row in df.iterrows():
    # ポップアップに表示するHTMLコンテンツを作成
    popup_html = f"""
    <b>Trip ID:</b> {row['id']}<br>
    <b>TimeLoss Diff:</b> {row['timeloss_diff']:.2f} 秒<br>
    <b>Depart Coords:</b> ({row['depart_lat']:.4f}, {row['depart_lon']:.4f})
    """
    
    # CircleMarkerを作成
    folium.CircleMarker(
        location=[row['depart_lat'], row['depart_lon']],
        radius=2,  # マーカーの半径を小さく変更 (5 -> 2)
        color=row['color'],
        fill=True,
        fill_color=row['color'],
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m) # 追加先を marker_cluster から m に変更


# --- 4. 凡例の追加 ---

# 地図に凡例を追加するためのHTML/CSS
legend_html = '''
     <div style="position: fixed; 
     bottom: 50px; left: 50px; width: 180px; height: 90px; 
     border:2px solid grey; z-index:9999; font-size:14px;
     background-color: white;
     ">&nbsp; <b>凡例 (TimeLossの差)</b><br>
     &nbsp; <i class="fa fa-circle" style="color:red"></i>&nbsp; 悪化 (> 0)<br>
     &nbsp; <i class="fa fa-circle" style="color:blue"></i>&nbsp; 改善 (< 0)<br>
     &nbsp; <i class="fa fa-circle" style="color:green"></i>&nbsp; 変化なし (= 0)</div>
     '''
m.get_root().html.add_child(folium.Element(legend_html))


# --- 5. HTMLファイルとして保存 ---

output_html = '250930/data/departure_timeloss_map_4.html'
m.save(output_html)

print(f"\n処理が完了しました！ ✨")
print(f"'{output_html}' をWebブラウザで開いて地図を確認してください。")