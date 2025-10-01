import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

# 1. データの読み込みと準備
csv_file = '250930/data/tripinfo_4.csv'
df = pd.read_csv(csv_file)
df['timeloss_diff'] = df['step4_timeLoss'] - df['step1_timeLoss']

# 2. 5秒間隔での集計
min_val = df['timeloss_diff'].min()
max_val = df['timeloss_diff'].max()
bins = np.arange(np.floor(min_val / 50) * 50, np.ceil(max_val / 50) * 50 + 50, 50)
df['binned'] = pd.cut(df['timeloss_diff'], bins=bins, right=False)
grouped_data = df.groupby('binned')['timeloss_diff'].agg(['sum', 'size']).reset_index()
grouped_data['midpoint'] = grouped_data['binned'].apply(lambda x: x.mid).astype(float)
grouped_data = grouped_data.sort_values('midpoint').dropna()

# 3. グラフ描画の準備 (y軸は1つのみ)
fig, ax1 = plt.subplots(figsize=(14, 8))

# 4. x軸の正負でデータを分割
neg_data = grouped_data[grouped_data['midpoint'] < 0]
pos_data = grouped_data[grouped_data['midpoint'] > 0]

# --- ここからが変更点 ---

# 5. 頻度(size)を棒グラフ(sum)のスケールに合わせるためのスケーリング処理
# 正のエリアのスケーリング
if not pos_data.empty and pos_data['size'].max() > 0:
    # 棒グラフの最大値
    max_bar_pos = pos_data['sum'].max()
    # 頻度の最大値
    max_freq_pos = pos_data['size'].max()
    # スケール係数 (頻度の最大値が棒の最大値の80%になるように)
    scale_factor_pos = (max_bar_pos * 0.8) / max_freq_pos
    # スケールを適用
    scaled_freq_pos = pos_data['size'] * scale_factor_pos
else:
    scaled_freq_pos = pd.Series(dtype='float64')

# 負のエリアのスケーリング
if not neg_data.empty and neg_data['size'].max() > 0:
    # 棒グラフの最小値（負の値）
    min_bar_neg = neg_data['sum'].min()
    # 頻度の最大値
    max_freq_neg = neg_data['size'].max()
    # スケール係数 (頻度の最大値が棒の最小値の80%になるように)
    scale_factor_neg = (min_bar_neg * 0.8) / max_freq_neg
    # スケールを適用 (値が負になり、グラフが下半分に描画される)
    scaled_freq_neg = neg_data['size'] * scale_factor_neg
else:
    scaled_freq_neg = pd.Series(dtype='float64')

# --- 変更点ここまで ---

# 6. 棒グラフ（差の合計値）を描画
ax1.bar(neg_data['midpoint'], neg_data['sum'], width=20, color='dodgerblue', alpha=0.7)
ax1.bar(pos_data['midpoint'], pos_data['sum'], width=20, color='orangered', alpha=0.7)

# 7. スケール調整した折れ線グラフ（頻度）を描画
ax1.plot(neg_data['midpoint'], scaled_freq_neg, color='deepskyblue', marker='o', linestyle='--')
ax1.plot(pos_data['midpoint'], scaled_freq_pos, color='tomato', marker='o', linestyle='--')


# 8. グラフの装飾
ax1.set_title('TimeLossの差（合計値と頻度）の分布（5秒間隔）', fontsize=16, fontweight='bold')
ax1.set_xlabel('TimeLossの差 [秒] (Step4 - Step1)', fontsize=12)
ax1.set_ylabel('TimeLoss差の合計値 [秒] / 頻度 (スケール調整済)', color='black', fontsize=12)
ax1.tick_params(axis='y', labelcolor='black')
ax1.axhline(0, color='black', linewidth=0.8)
ax1.axvline(0, color='black', linewidth=0.8, linestyle='-')
ax1.grid(axis='y', linestyle='--', alpha=0.6)

ax1.set_xlim(-3000, 3000)

# 9. 凡例の作成
legend_elements = [
    mpatches.Patch(color='orangered', alpha=0.7, label='TimeLoss合計値 (悪化)'),
    mpatches.Patch(color='dodgerblue', alpha=0.7, label='TimeLoss合計値 (改善)'),
    Line2D([0], [0], color='tomato', marker='o', linestyle='--', label='頻度 (悪化, スケール調整済)'),
    Line2D([0], [0], color='deepskyblue', marker='o', linestyle='--', label='頻度 (改善, スケール調整済)')
]
ax1.legend(handles=legend_elements, loc='upper left', fontsize=10)

fig.tight_layout()
plt.show()