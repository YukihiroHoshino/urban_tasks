# QVK plot

## README
'''
this file is making "QK plot" of "each edge" with color dradation indicating "hour"
like "Q-K図: Kakujo_nobori"
- with color dradation indicating "hour"
- same x-lim and y-lim (you can set the value, or max value of all the edge)
'''

## import
import xml.etree.ElementTree as ET
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import japanize_matplotlib
import os
import re
from collections import defaultdict

## save figures
save_dir = "figure_QK_fixedlim"
os.makedirs(save_dir, exist_ok=True)  

## read file
path_to_result = 'data/20250129plain.xml'
tree = ET.parse(path_to_result)
root = tree.getroot()

## setting xlim and ylim
x_max_user = 30   # or None
y_max_user = 500  # or None

all_k = []
all_flow_ma = []
grouped_dict = {}

## Step 1: Aggregate data by prefix
prefix_dict = defaultdict(lambda: {"begin": [], "flow": [], "vel": []})

### 集計用
total_prefix_count = 0
success_count = 0
error_k_zero_count = 0
error_flow_ma_nan_count = 0

### weighted hermonic_mean
def weighted_harmonic_mean(velocities, flows):
    # 欠損またはゼロの速度を除外
    valid = (velocities > 0) & velocities.notna() & flows.notna()
    velocities = velocities[valid]
    flows = flows[valid]

    if len(velocities) == 0:
        return float('nan')

    numerator = flows.sum()
    denominator = (flows / velocities).sum()
    return numerator / denominator if denominator != 0 else float('nan')

### culcurate
for data in root.findall('interval'):
    begin = float(data.get('begin'))  # 秒単位
    hour = int(begin) // 3600
    id_full = data.get('id')
    prefix = re.sub(r'_\d+_\d+$', '', id_full)

    n = float(data.get('flow'))
    v = float(data.get('speed')) * 3.6  # m/s → km/h

    prefix_dict[prefix]["begin"].append(begin)
    prefix_dict[prefix]["flow"].append((begin, n))
    prefix_dict[prefix]["vel"].append((begin, v))

for prefix, values in prefix_dict.items():
    total_prefix_count += 1
    df_flow = pd.DataFrame(values["flow"], columns=["begin", "flow"])
    df_vel = pd.DataFrame(values["vel"], columns=["begin", "vel"])

    df_merge = pd.merge(df_flow, df_vel, on="begin")
    grouped = df_merge.groupby("begin").apply(
        lambda g: pd.Series({
            "flow": g["flow"].sum(),
            "vel": weighted_harmonic_mean(g["vel"], g["flow"])
        }),
        include_groups=False
    ).reset_index()

    ### 妥当性を確認
    grouped["k"] = grouped["flow"] / grouped["vel"]
    grouped["hour"] = grouped["begin"] // 3600
    grouped = grouped[grouped["k"] > 0.01]

    if grouped.empty:
        print(f"[ERROR] {prefix}: 有効な密度データが存在しません（k <= 0.01 ばかり）")
        error_k_zero_count += 1
        continue

    grouped["flow_ma"] = grouped["flow"].rolling(window=5).mean()
    valid = grouped.dropna(subset=["flow_ma"])

    if valid.empty:
        print(f"[ERROR] {prefix}: 有効な移動平均データが存在しません（flow_ma が NaN）")
        error_flow_ma_nan_count += 1
        continue

    all_k.extend(valid["k"].tolist())
    all_flow_ma.extend(valid["flow_ma"].tolist())
    grouped_dict[prefix] = valid
    success_count += 1

## culcurate xlim and ylim (user setting or automatic)
xmax = x_max_user if x_max_user is not None else (max(all_k) * 1.05 if all_k else 100)
ymax = y_max_user if y_max_user is not None else (max(all_flow_ma) * 1.05 if all_flow_ma else 100)

## Step 2: plot figs
cmap = plt.colormaps['coolwarm']
norm = mcolors.Normalize(vmin=0, vmax=23)

for prefix, grouped in grouped_dict.items():
    fig, ax = plt.subplots(figsize=(7, 6))
    scatter = ax.scatter(
        grouped["k"],
        grouped["flow_ma"],
        c=grouped["hour"],
        cmap=cmap,
        norm=norm,
        s=15
    )

    ax.set_xlabel("密度 K [台/km]")
    ax.set_ylabel("交通量 Q [台/h]")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_title(f"Q-K図: {prefix}")

    cbar = plt.colorbar(scatter, ax=ax, ticks=range(0, 24, 3))
    cbar.set_label("時間帯")
    cbar.set_ticks(range(0, 24, 3))
    cbar.set_ticklabels([f"{hour}:00" for hour in range(0, 24, 3)])

    plt.tight_layout()
    save_path = os.path.join(save_dir, f"{prefix}.png")
    plt.savefig(save_path)
    plt.close()

### totalization
print("\n=== 集計結果 ===")
print(f"全プリフィックス数: {total_prefix_count}")
print(f"正常に出力できたプリフィックス数: {success_count}")
print(f"[ERROR] 有効な密度データが存在しません: {error_k_zero_count}")
print(f"[ERROR] 有効な移動平均データが存在しません: {error_flow_ma_nan_count}")