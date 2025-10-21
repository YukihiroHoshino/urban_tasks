import pandas as pd
import folium

# --- 1. データの読み込みと準備 ---

csv_file = '250930/data/tripinfo_with_coords_BRT.csv'
print(f"'{csv_file}' を読み込んでいます...")
df = pd.read_csv(csv_file)

# 出発地または到着地の座標が欠損している行を削除
original_count = len(df)
df.dropna(subset=['depart_lon', 'depart_lat', 'arrival_lon', 'arrival_lat'], inplace=True)
print(f"座標が欠損していた {original_count - len(df)} 件のデータを除外しました。")

# --- ★★★ 変更点：移動距離(routeLength)によるフィルタリング ★★★ ---
# フィルタリングのしきい値を設定 (単位: メートル)
# この値を変更することで、描画対象のトリップの長さを調整できます。
route_length_threshold = 5000

print(f"\n移動距離が {route_length_threshold}m 以上のトリップのみを抽出します...")
count_before_filter = len(df)
df = df[df['step1_routeLength'] <= route_length_threshold].copy() # .copy()を追加してSettingWithCopyWarningを回避
print(f"フィルタリングの結果、 {count_before_filter}件 から {len(df)}件 のトリップが残りました。")
# --- ★★★ 変更ここまで ★★★ ---


# 10000件にランダムサンプリング
if len(df) > 1000:
    print(f"\nデータが多いため、1000件にランダムサンプリングします。")
    df_sampled = df.sample(n=5000, random_state=999) # random_stateで結果を固定
    print(f"サンプリング後のデータ件数: {len(df_sampled)}件")
else:
    df_sampled = df

# TimeLossの差を計算し、色を決定
df_sampled['timeloss_diff'] = df_sampled['step4_timeLoss'] - df_sampled['step1_timeLoss']

def assign_color(diff):
    if diff > 0:
        return '#9736ff'    # 悪化
    elif diff < 0:
        return '#ff861c'   # 改善
    else:
        return 'green'  # 変化なし

df_sampled['color'] = df_sampled['timeloss_diff'].apply(assign_color)


# --- 2. ベースマップの作成 ---

# 地図の中心を、出発地と到着地の座標の平均に設定
center_lat = (df_sampled['depart_lat'].mean() + df_sampled['arrival_lat'].mean()) / 2
center_lon = (df_sampled['depart_lon'].mean() + df_sampled['arrival_lon'].mean()) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')

print("\n地図上にトリップの直線を描画しています...")

# --- 3. 直線の描画 ---

# データフレームの各行をループして、地図に直線を追加
for idx, row in df_sampled.iterrows():
    # ポップアップに表示するHTMLコンテンツを作成
    popup_html = f"""
    <b>Trip ID:</b> {row['id']}<br>
    <b>Route Length:</b> {row['step1_routeLength']:.2f} m<br> <b>TimeLoss Diff:</b> {row['timeloss_diff']:.2f} 秒<br>
    <b>From:</b> ({row['depart_lat']:.4f}, {row['depart_lon']:.4f})<br>
    <b>To:</b> ({row['arrival_lat']:.4f}, {row['arrival_lon']:.4f})
    """
    
    # PolyLine（直線）を作成
    folium.PolyLine(
        locations=[(row['depart_lat'], row['depart_lon']), (row['arrival_lat'], row['arrival_lon'])],
        color=row['color'],
        weight=1.5,
        opacity=0.8,
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m)

# --- 4. 凡例の追加 ---

legend_html = '''
     <div style="position: fixed; 
     bottom: 50px; left: 50px; width: 180px; height: 90px; 
     border:2px solid grey; z-index:9999; font-size:14px;
     background-color: white;
     ">&nbsp; <b>凡例 (TimeLossの差)</b><br>
     &nbsp; <i class="fa fa-minus" style="color:#9736ff"></i>&nbsp; 悪化 (> 0)<br>
     &nbsp; <i class="fa fa-minus" style="color:#ff861c"></i>&nbsp; 改善 (< 0)<br>
     &nbsp; <i class="fa fa-minus" style="color:green"></i>&nbsp; 変化なし (= 0)</div>
     '''
m.get_root().html.add_child(folium.Element(legend_html))


# --- 5. HTMLファイルとして保存 ---

output_html = '250930/data/trip_lines_map_BRT_all.html' # ★新しいファイル名
m.save(output_html)

print(f"\n処理が完了しました！ ✨")
print(f"'{output_html}' をWebブラウザで開いて地図を確認してください。")