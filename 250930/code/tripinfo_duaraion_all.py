import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import japanize_matplotlib # 日本語表示を有効化

# 1. データの読み込み
csv_file = '250930/data/tripinfo_4.csv'
df = pd.read_csv(csv_file)

# 2. Durationの差を計算
df['duration_diff'] = df['step4_duration'] - df['step1_duration']

# 3. 差の値ごとに頻度を計算し、差の大きさでソート
duration_counts = df['duration_diff'].value_counts().sort_index()

# 4. グラフの描画準備
fig, ax = plt.subplots(figsize=(12, 7))

# 差の値（x軸）と頻度（y軸）
x_values = duration_counts.index
y_values = duration_counts.values

# 差が正か負かゼロかに応じて色を決定
colors = []
for val in x_values:
    if val > 0:
        colors.append('orangered') # 悪化（Durationが増加）
    elif val < 0:
        colors.append('dodgerblue') # 改善（Durationが減少）
    else:
        colors.append('gray') # 変化なし

# 5. 棒グラフを作成
ax.bar(x_values, y_values, color=colors, width=0.8, align='center', edgecolor='black', alpha=0.8)

# 6. 縦軸を対数スケールに変更
ax.set_yscale('log')

# 6. グラフの装飾
ax.set_title('Durationの差（Step4 - Step1）の頻度分布', fontsize=16, fontweight='bold')
ax.set_xlabel('Durationの差 [秒] (Step4 - Step1)', fontsize=12)
ax.set_ylabel('頻度（トリップ数）', fontsize=12)

# y軸にグリッド線を追加
ax.grid(axis='y', linestyle='--', alpha=0.7)
# x=0の位置に基準となる黒線を追加
ax.axvline(0, color='black', linewidth=0.8, linestyle='-')

# 凡例（凡例を分かりやすくするために手動で作成）
legend_patches = [
    mpatches.Patch(color='orangered', label='Durationが増加 (悪化)'),
    mpatches.Patch(color='dodgerblue', label='Durationが減少 (改善)'),
    mpatches.Patch(color='gray', label='変化なし')
]
ax.legend(handles=legend_patches, fontsize=10)

# グラフのレイアウトを調整
plt.tight_layout()

# 7. グラフの表示
plt.show()

# グラフを画像ファイルとして保存する場合
# fig.savefig('duration_difference_histogram.png', dpi=300)

'''
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import japanize_matplotlib # 日本語表示を有効化

# 1. データの読み込み
csv_file = '250930/data/tripinfo_4.csv'
df = pd.read_csv(csv_file)

# 2. Durationの差を計算
df['duration_diff'] = df['step4_duration'] - df['step1_duration']

# 3. 差の値ごとに頻度を計算し、差の大きさでソート
duration_counts = df['duration_diff'].value_counts().sort_index()

# 4. グラフの描画準備
fig, ax = plt.subplots(figsize=(12, 7))

# --- 折れ線グラフの色分けのためのデータ分割 ---
# グラフが中央(x=0)で途切れないように、0のデータ点を両方の線に追加する
point_at_zero = duration_counts[duration_counts.index == 0]

# 負のデータ点 (改善)
negative_counts = duration_counts[duration_counts.index < 0]
negative_counts = pd.concat([negative_counts, point_at_zero])

# 正のデータ点 (悪化)
positive_counts = duration_counts[duration_counts.index > 0]
positive_counts = pd.concat([point_at_zero, positive_counts])

# ゼロのデータ点 (変化なし)
zero_count = duration_counts[duration_counts.index == 0]

# 5. 各セグメントを折れ線グラフとしてプロット
ax.plot(negative_counts.index, negative_counts.values, color='dodgerblue', marker='o', linestyle='-', label='Durationが減少 (改善)')
ax.plot(positive_counts.index, positive_counts.values, color='orangered', marker='o', linestyle='-', label='Durationが増加 (悪化)')
# 変化なしの点はマーカーのみプロット
if not zero_count.empty:
    ax.plot(zero_count.index, zero_count.values, color='gray', marker='o', markersize=8, linestyle='None', label='変化なし')


# 6. 縦軸を対数スケールに変更
ax.set_yscale('log')

# 7. グラフの装飾
ax.set_title('Durationの差（Step4 - Step1）の頻度分布（対数軸・折れ線）', fontsize=16, fontweight='bold')
ax.set_xlabel('Durationの差 [秒] (Step4 - Step1)', fontsize=12)
ax.set_ylabel('頻度（トリップ数） [対数スケール]', fontsize=12)

# グリッド線を追加
ax.grid(True, which="both", linestyle='--', alpha=0.6)
# x=0の位置に基準となる黒線を追加
ax.axvline(0, color='black', linewidth=0.8, linestyle='-')

# 凡例を表示
ax.legend(fontsize=10)

# グラフのレイアウトを調整
plt.tight_layout()

# 8. グラフの表示
plt.show()

# グラフを画像ファイルとして保存する場合
# fig.savefig('duration_difference_line_log.png', dpi=300)
'''