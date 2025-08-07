import pandas as pd
import matplotlib.pyplot as plt

try:
    # sunday_trips.csvファイルを直接読み込む
    df = pd.read_csv('250724/data/sunday_trips.csv')

    # ETC2.0プローブデータの仕様に基づく車種コードと名称のマッピング
    vehicle_type_map = {
        0: 'keinirin',
        1: 'ogata',
        2: 'futuu',
        3: 'kogata',
        4: 'kei',
        5: 'others'
    }

    # 自動車の種別ごとのトリップ数を計算
    vehicle_counts = df['自動車の種別'].value_counts()

    # 集計結果のコードを、マッピングを使って日本語の車種名に変換
    # マップにないコードはそのまま表示する
    vehicle_counts.index = vehicle_counts.index.map(lambda x: vehicle_type_map.get(x, f'不明なコード({x})'))

    # グラフの作成
    plt.figure(figsize=(10, 6))
    vehicle_counts.plot(kind='bar', color='skyblue', edgecolor='black')

    # グラフの装飾
    plt.title('trpis # vs car_stype', fontsize=16)
    plt.xlabel('car_type', fontsize=12)
    plt.ylabel('trips #', fontsize=12)
    plt.xticks(rotation=45, ha='right') # ラベルが重ならないように回転
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout() # レイアウトを自動調整

    # グラフを表示
    plt.show()

    # 集計結果の表示
    print("自動車の種別ごとのトリップ数:")
    print(vehicle_counts)

except FileNotFoundError:
    print("エラー: 'sunday_trips.csv' が見つかりません。コードと同じディレクトリにファイルを配置してください。")
except Exception as e:
    print(f"エラーが発生しました: {e}")