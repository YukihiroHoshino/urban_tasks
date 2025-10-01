import pandas as pd
import folium
import matplotlib.pyplot as plt
import seaborn as sns
import math

# --- 1. CSVの読み込み ---
df = pd.read_csv("departure_times.csv")

# --- 2. 出発時間を負の分数に変換 ---
def time_str_to_minutes(time_str):
    sign = -1 if time_str.startswith('-') else 1
    h, m, s = map(int, time_str.strip('-+').split(':'))
    return sign * (h * 60 + m + s / 60)

df['departure_minutes'] = df['optimal_departure_time'].apply(time_str_to_minutes)

# --- 3. 5分刻みでビニング ---
df['time_bin'] = df['departure_minutes'].apply(lambda x: math.floor(x / 5) * 5)

# --- 4. ビンごとに色を割り当て ---
unique_bins = sorted(df['time_bin'].unique())
palette = sns.color_palette("viridis", n_colors=len(unique_bins))
bin_color_map = dict(zip(unique_bins, palette))

df['color_rgb'] = df['time_bin'].map(bin_color_map)
df['color_hex'] = df['color_rgb'].apply(lambda rgb: '#%02x%02x%02x' % tuple(int(c * 255) for c in rgb))

# --- 5. 地図作成 ---
center_lat = df['latitude'].mean()
center_lon = df['longitude'].mean()
m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

for _, row in df.iterrows():
    folium.CircleMarker(
        location=[row['latitude'], row['longitude']],
        radius=7,
        popup=f"{row['location_name']}: {row['optimal_departure_time']} ({int(abs(row['time_bin']))}分前)",
        color=row['color_hex'],
        fill=True,
        fill_color=row['color_hex'],
        fill_opacity=0.7,
        opacity=0.7
    ).add_to(m)

# --- 6. 凡例追加（代表時間のみを表示）---
legend_html = """
<div style="
    position: fixed;
    bottom: 50px;
    left: 50px;
    width: 200px;
    height: auto;
    z-index:9999;
    font-size:14px;
    background-color: white;
    border:2px solid grey;
    border-radius:6px;
    padding: 10px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
">
    <b>出発タイミング</b><br>
"""

# 時間ラベルは「n分前」などと表示
for bin_val in unique_bins:
    hex_color = '#%02x%02x%02x' % tuple(int(c * 255) for c in bin_color_map[bin_val])
    label = f"{int(abs(bin_val))}min"
    legend_html += f"""
    <i style="background:{hex_color};width:18px;height:18px;float:left;margin-right:8px;opacity:0.8;"></i>
    {label}<br>
    """

legend_html += "</div>"

m.get_root().html.add_child(folium.Element(legend_html))

# --- 7. 地図保存 ---
m.save("optimal_departure_map.html")
print("地図を保存しました。")


