import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches
import seaborn as sns
import japanize_matplotlib # 日本語表示を有効化

# --- 1. データの読み込みと準備 ---
csv_file = '250930/data/tripinfo_BRT.csv'
df = pd.read_csv(csv_file)

# --- 移動距離(routeLength)によるフィルタリング ---
route_length_threshold = 500
print(f"移動距離が {route_length_threshold}m 以上のトリップのみを対象とします。")
count_before_filter = len(df)
df = df[df['step1_routeLength'] >= route_length_threshold].copy()
print(f"フィルタリングの結果、 {count_before_filter}件 から {len(df)}件 のデータが残りました。\n")

# --- 2. 単位長さあたりのTimeLossを計算 ---
df = df[df['step1_routeLength'] > 1.0].copy()
df = df[df['step4_routeLength'] > 1.0].copy()
df['tl_per_rl_s1'] = df['step1_timeLoss'] / df['step1_routeLength']
df['tl_per_rl_s4'] = df['step4_timeLoss'] / df['step4_routeLength']

'''
# --- 3. ボックスプロットによる外れ値の可視化 ---
plt.figure(figsize=(8, 6))
sns.boxplot(data=df[['tl_per_rl_s1', 'tl_per_rl_s4']])
plt.title(f'単位長さあたりTimeLossの分布（移動距離 >= {route_length_threshold}m）')
plt.ylabel('TimeLoss / RouteLength')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.show()
'''

# --- 4. IQR法による外れ値の除去 ---
Q1_s1 = df['tl_per_rl_s1'].quantile(0.25)
Q3_s1 = df['tl_per_rl_s1'].quantile(0.75)
IQR_s1 = Q3_s1 - Q1_s1
lower_bound_s1 = Q1_s1 - 1.5 * IQR_s1
upper_bound_s1 = Q3_s1 + 1.5 * IQR_s1

Q1_s4 = df['tl_per_rl_s4'].quantile(0.25)
Q3_s4 = df['tl_per_rl_s4'].quantile(0.75)
IQR_s4 = Q3_s4 - Q1_s4
lower_bound_s4 = Q1_s4 - 1.5 * IQR_s4
upper_bound_s4 = Q3_s4 + 1.5 * IQR_s4

original_count = len(df)
df_filtered = df[
    (df['tl_per_rl_s1'] >= lower_bound_s1) & (df['tl_per_rl_s1'] <= upper_bound_s1) &
    (df['tl_per_rl_s4'] >= lower_bound_s4) & (df['tl_per_rl_s4'] <= upper_bound_s4)
].copy()
filtered_count = len(df_filtered)

print("--- 外れ値の除去結果 ---")
print(f"元のデータ数: {original_count}")
print(f"除去された外れ値の数: {original_count - filtered_count}")
print(f"外れ値除去後のデータ数: {filtered_count}\n")


# --- 5. 外れ値除去後のデータでグラフ作成処理 ---
df_filtered['timeloss_diff'] = df_filtered['step4_timeLoss'] - df_filtered['step1_timeLoss']

min_val = df_filtered['timeloss_diff'].min()
max_val = df_filtered['timeloss_diff'].max()
bins = np.arange(np.floor(min_val / 50) * 50, np.ceil(max_val / 50) * 50 + 50, 50)
df_filtered['binned'] = pd.cut(df_filtered['timeloss_diff'], bins=bins, right=False)
grouped_data = df_filtered.groupby('binned', observed=False)['timeloss_diff'].agg(['sum', 'size']).reset_index()
grouped_data['midpoint'] = grouped_data['binned'].apply(lambda x: x.mid).astype(float)
grouped_data = grouped_data.sort_values('midpoint').dropna()

# --- ★★★ 変更点：グラフを第一象限にまとめ、棒を並べて表示 ★★★ ---
grouped_data['midpoint_abs'] = grouped_data['midpoint'].abs()

# 悪化（正）と改善（負）のデータに分割
pos_data = grouped_data[grouped_data['midpoint'] >= 0][['midpoint_abs', 'sum', 'size']].rename(
    columns={'sum': 'sum_pos', 'size': 'size_pos'})
neg_data = grouped_data[grouped_data['midpoint'] < 0][['midpoint_abs', 'sum', 'size']].rename(
    columns={'sum': 'sum_neg', 'size': 'size_neg'})
neg_data['sum_neg'] = neg_data['sum_neg'].abs() # 棒グラフを正の向きにするために絶対値をとる

# 絶対値の階級をキーにしてデータを結合
plot_df = pd.merge(pos_data, neg_data, on='midpoint_abs', how='outer').fillna(0).sort_values('midpoint_abs')

# グラフ描画の準備
fig, ax1 = plt.subplots(figsize=(14, 8))
x = plot_df['midpoint_abs']
# 階級の幅から棒グラフ1本ずつの幅を計算
bin_width = x.diff().median() if not x.empty else 500
bar_width = bin_width * 0.4

# 棒グラフ（差の合計値）を並べて描画
ax1.bar(x - bar_width/2, plot_df['sum_pos'], width=bar_width, color='#9736ff', alpha=0.7, label='TimeLoss合計値 (悪化)')
ax1.bar(x + bar_width/2, plot_df['sum_neg'], width=bar_width, color='#ff861c', alpha=0.7, label='TimeLoss合計値 (改善)')

# 頻度(size)を棒グラフ(sum)のスケールに合わせるためのスケーリング処理
max_bar_val = max(plot_df['sum_pos'].max(), plot_df['sum_neg'].max()) if not plot_df.empty else 1
max_freq_val = max(plot_df['size_pos'].max(), plot_df['size_neg'].max()) if not plot_df.empty else 1

if max_freq_val > 0:
    scale_factor = (max_bar_val * 0.8) / max_freq_val
    scaled_freq_pos = plot_df['size_pos'] * scale_factor
    scaled_freq_neg = plot_df['size_neg'] * scale_factor
else:
    scaled_freq_pos = pd.Series(dtype='float64')
    scaled_freq_neg = pd.Series(dtype='float64')

# スケール調整した折れ線グラフ（頻度）を描画
ax1.plot(x, scaled_freq_pos, color='#46156b', marker='o', linestyle='--', label='頻度 (悪化, スケール調整済)')
ax1.plot(x, scaled_freq_neg, color='#c25e06', marker='o', linestyle='--', label='頻度 (改善, スケール調整済)')

# グラフの装飾
ax1.set_title(f'TimeLossの差の絶対値別分布（移動距離 >= {route_length_threshold}m, 外れ値除去後）', fontsize=16, fontweight='bold')
ax1.set_xlabel('TimeLossの差の絶対値 [秒]', fontsize=12) # ラベルを変更
ax1.set_ylabel('TimeLoss差の合計値 [秒] / 頻度', color='black', fontsize=12)
ax1.tick_params(axis='y', labelcolor='black')
ax1.axhline(0, color='black', linewidth=0.8)
ax1.grid(axis='y', linestyle='--', alpha=0.7)
ax1.set_xlim(left=0) # X軸の最小値を0に設定
ax1.set_xlim(right=3500)

# 凡例はプロット時にlabel引数で指定したため、自動生成
ax1.legend(loc='upper right', fontsize=10)

fig.tight_layout()
fig.savefig('250930/fig/timeloss_BRT_all.png', dpi=300)
#plt.show()

