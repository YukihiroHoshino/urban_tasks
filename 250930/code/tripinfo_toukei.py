import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib

# --- 0. 初期設定 ---
# 統計的有意水準 (一般的に0.05が用いられる)
SIGNIFICANCE_LEVEL = 0.05

# --- 1. データの準備 ---
csv_file = '250930/data/tripinfo_4.csv'
df = pd.read_csv(csv_file)

# timeLossの差を計算 (Step4 - Step1)
df['timeloss_diff'] = df['step4_timeLoss'] - df['step1_timeLoss']

# --- 2. データの可視化 ---
plt.figure(figsize=(18, 5))

# Step1とStep4の分布を重ねて表示
plt.subplot(1, 3, 1)
sns.histplot(df['step1_timeLoss'], color='blue', kde=True, label='Step1 TimeLoss', stat="density")
sns.histplot(df['step4_timeLoss'], color='red', kde=True, label='Step4 TimeLoss', stat="density")
plt.title('TimeLossの分布（処理前）')
plt.legend()

# 差の分布を表示
plt.subplot(1, 3, 2)
sns.histplot(df['timeloss_diff'], color='green', kde=True)
plt.title('TimeLossの差の分布（処理前）')

# 箱ひげ図で外れ値を確認
plt.subplot(1, 3, 3)
sns.boxplot(data=df[['timeloss_diff']])
plt.title('TimeLossの差の箱ひげ図')
plt.tight_layout()
plt.show()


# --- 3. 外れ値の除外 (IQR法) ---
Q1 = df['timeloss_diff'].quantile(0.25)
Q3 = df['timeloss_diff'].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

# 外れ値を除外した新しいDataFrameを作成
df_filtered = df[(df['timeloss_diff'] >= lower_bound) & (df['timeloss_diff'] <= upper_bound)]

print("--- 外れ値の除外 ---")
print(f"元のデータ数: {len(df)}")
print(f"除外された外れ値の数: {len(df) - len(df_filtered)}")
print(f"外れ値除外後のデータ数: {len(df_filtered)}\n")


# --- 4. 正規性の検定 (シャピロ・ウィルク検定) ---
# 帰無仮説: 「データは正規分布に従う」
shapiro_stat, shapiro_p_value = stats.shapiro(df_filtered['timeloss_diff'])

print("--- 正規性の検定（シャピロ・ウィルク検定） ---")
print(f"p値: {shapiro_p_value:.4f}")

# Q-Qプロットで視覚的に確認
plt.figure(figsize=(6, 6))
stats.probplot(df_filtered['timeloss_diff'], dist="norm", plot=plt)
plt.title('Q-Qプロット（外れ値除外後）')
plt.show()

is_normal = shapiro_p_value > SIGNIFICANCE_LEVEL
if is_normal:
    print("p値 > 0.05 のため、正規分布に従うと仮定します。\n")
else:
    print("p値 <= 0.05 のため、正規分布に従わないと判断します。\n")


# --- 5. 統計的仮説検定の実施 ---
# 帰無仮説(H0): 「Step1とStep4のtimeLossに差はない」(差の分布の中央値が0)
# 対立仮説(H1): 「Step1とStep4のtimeLossに差がある」(差の分布の中央値が0ではない)
print("--- 統計的仮説検定 ---")
if is_normal:
    print(">> 対応のあるt検定 を実行します。")
    # 対応のあるt検定
    t_stat, p_value = stats.ttest_rel(
        df_filtered['step1_timeLoss'],
        df_filtered['step4_timeLoss']
    )
else:
    print(">> ウィルコクソンの符号順位検定 を実行します。")
    # ウィルコクソンの符号順位検定
    # 差が0のデータは検定に影響するため除外(zero_method='prune')
    wilcoxon_stat, p_value = stats.wilcoxon(df_filtered['timeloss_diff'])

print(f"検定結果のp値: {p_value:.4f}")


# --- 6. 結果の解釈と結論 ---
print("\n--- 結論 ---")
if p_value < SIGNIFICANCE_LEVEL:
    print(f"p値が有意水準 {SIGNIFICANCE_LEVEL} より小さいため、帰無仮説は棄却されます。")
    print("結論: Step1とStep4のTimeLossには、統計的に有意な差があると言えます。✅")
else:
    print(f"p値が有意水準 {SIGNIFICANCE_LEVEL} 以上であるため、帰無仮説は棄却されません。")
    print("結論: Step1とStep4のTimeLossには、統計的に有意な差があるとは言えません。")