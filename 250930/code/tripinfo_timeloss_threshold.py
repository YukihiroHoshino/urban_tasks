import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches
import seaborn as sns
import japanize_matplotlib # 日本語表示を有効化

# --- 1. データの読み込みと準備 ---
csv_file = '250930/data/tripinfo_4.csv'
df = pd.read_csv(csv_file)

# --- ★★★ 変更点：移動距離(routeLength)によるフィルタリング ★★★ ---
route_length_threshold = 0
print(f"移動距離が {route_length_threshold}m 以上のトリップのみを対象とします。")
count_before_filter = len(df)
df = df[df['step1_routeLength'] >= route_length_threshold].copy()
print(f"フィルタリングの結果、 {count_before_filter}件 から {len(df)}件 のデータが残りました。\n")
# --- ★★★ 変更ここまで ★★★ ---


# --- 2. 単位長さあたりのTimeLossを計算 ---
# routeLengthが0または極端に小さい場合のゼロ除算エラーを防ぐ
# (上記のフィルタリングでカバーされますが、念のため残します)
df = df[df['step1_routeLength'] > 1.0].copy()
df = df[df['step4_routeLength'] > 1.0].copy()

df['tl_per_rl_s1'] = df['step1_timeLoss'] / df['step1_routeLength']
df['tl_per_rl_s4'] = df['step4_timeLoss'] / df['step4_routeLength']

# --- 3. ボックスプロットによる外れ値の可視化 ---
plt.figure(figsize=(8, 6))
sns.boxplot(data=df[['tl_per_rl_s1', 'tl_per_rl_s4']])
plt.title(f'単位長さあたりTimeLossの分布（移動距離 >= {route_length_threshold}m）')
plt.ylabel('TimeLoss / RouteLength')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.show()

# --- 4. IQR法による外れ値の除去 ---
# Step1の指標に対する外れ値の範囲を計算
Q1_s1 = df['tl_per_rl_s1'].quantile(0.25)
Q3_s1 = df['tl_per_rl_s1'].quantile(0.75)
IQR_s1 = Q3_s1 - Q1_s1
lower_bound_s1 = Q1_s1 - 1.5 * IQR_s1
upper_bound_s1 = Q3_s1 + 1.5 * IQR_s1

# Step4の指標に対する外れ値の範囲を計算
Q1_s4 = df['tl_per_rl_s4'].quantile(0.25)
Q3_s4 = df['tl_per_rl_s4'].quantile(0.75)
IQR_s4 = Q3_s4 - Q1_s4
lower_bound_s4 = Q1_s4 - 1.5 * IQR_s4
upper_bound_s4 = Q3_s4 + 1.5 * IQR_s4

# Step1とStep4の両方で外れ値でないトリップのみを抽出
original_count = len(df)
df_filtered = df[
    (df['tl_per_rl_s1'] >= lower_bound_s1) & (df['tl_per_rl_s1'] <= upper_bound_s1) &
    (df['tl_per_rl_s4'] >= lower_bound_s4) & (df['tl_per_rl_s4'] <= upper_bound_s4)
].copy() # .copy() を付けて警告を回避
filtered_count = len(df_filtered)

print("--- 外れ値の除去結果 ---")
print(f"元のデータ数: {original_count}")
print(f"除去された外れ値の数: {original_count - filtered_count}")
print(f"外れ値除去後のデータ数: {filtered_count}\n")


# --- 5. 外れ値除去後のデータでグラフ作成処理 ---
# ここからの処理は、すべて外れ値除去後の `df_filtered` を使用します
df_filtered['timeloss_diff'] = df_filtered['step4_timeLoss'] - df_filtered['step1_timeLoss']

# 5秒間隔での集計
min_val = df_filtered['timeloss_diff'].min()
max_val = df_filtered['timeloss_diff'].max()
bins = np.arange(np.floor(min_val / 500) * 500, np.ceil(max_val / 500) * 500 + 500, 500)
df_filtered['binned'] = pd.cut(df_filtered['timeloss_diff'], bins=bins, right=False)
grouped_data = df_filtered.groupby('binned')['timeloss_diff'].agg(['sum', 'size']).reset_index()
grouped_data['midpoint'] = grouped_data['binned'].apply(lambda x: x.mid).astype(float)
grouped_data = grouped_data.sort_values('midpoint').dropna()

# グラフ描画の準備 (y軸は1つのみ)
fig, ax1 = plt.subplots(figsize=(14, 8))

# x軸の正負でデータを分割
neg_data = grouped_data[grouped_data['midpoint'] < 0]
pos_data = grouped_data[grouped_data['midpoint'] > 0]

# 頻度(size)を棒グラフ(sum)のスケールに合わせるためのスケーリング処理
if not pos_data.empty and pos_data['size'].max() > 0:
    max_bar_pos = pos_data['sum'].max()
    max_freq_pos = pos_data['size'].max()
    scale_factor_pos = (max_bar_pos * 0.8) / max_freq_pos
    scaled_freq_pos = pos_data['size'] * scale_factor_pos
else:
    scaled_freq_pos = pd.Series(dtype='float64')

if not neg_data.empty and neg_data['size'].max() > 0:
    min_bar_neg = neg_data['sum'].min()
    max_freq_neg = neg_data['size'].max()
    scale_factor_neg = (min_bar_neg * 0.8) / max_freq_neg
    scaled_freq_neg = neg_data['size'] * scale_factor_neg
else:
    scaled_freq_neg = pd.Series(dtype='float64')

# 棒グラフ（差の合計値）を描画
ax1.bar(neg_data['midpoint'], neg_data['sum'], width=200, color='dodgerblue', alpha=0.7)
ax1.bar(pos_data['midpoint'], pos_data['sum'], width=200, color='orangered', alpha=0.7)

# スケール調整した折れ線グラフ（頻度）を描画
ax1.plot(neg_data['midpoint'], scaled_freq_neg, color='deepskyblue', marker='o', linestyle='--')
ax1.plot(pos_data['midpoint'], scaled_freq_pos, color='tomato', marker='o', linestyle='--')

# グラフの装飾
ax1.set_title(f'TimeLossの差の分布（移動距離 >= {route_length_threshold}m, 外れ値除去後）', fontsize=16, fontweight='bold')
ax1.set_xlabel('TimeLossの差 [秒] (Step4 - Step1)', fontsize=12)
ax1.set_ylabel('TimeLoss差の合計値 [秒] / 頻度 (スケール調整済)', color='black', fontsize=12)
ax1.tick_params(axis='y', labelcolor='black')
ax1.axhline(0, color='black', linewidth=0.8)
ax1.axvline(0, color='black', linewidth=0.8, linestyle='-')
ax1.grid(axis='y', linestyle='--', alpha=0.7)
ax1.set_xlim(-10000, 10000)

# 凡例の作成
legend_elements = [
    mpatches.Patch(color='orangered', alpha=0.7, label='TimeLoss合計値 (悪化)'),
    mpatches.Patch(color='dodgerblue', alpha=0.7, label='TimeLoss合計値 (改善)'),
    Line2D([0], [0], color='tomato', marker='o', linestyle='--', label='頻度 (悪化, スケール調整済)'),
    Line2D([0], [0], color='deepskyblue', marker='o', linestyle='--', label='頻度 (改善, スケール調整済)')
]
ax1.legend(handles=legend_elements, loc='upper left', fontsize=10)

fig.tight_layout()
plt.show()