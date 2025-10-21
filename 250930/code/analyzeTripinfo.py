import xml.etree.ElementTree as ET
import pandas as pd

def parse_tripinfo(xml_file, columns_to_extract):
    """
    SUMOのtripinfo.xmlファイルを解析し、指定されたカラムを抽出して
    pandasのDataFrameとして返す関数。

    Args:
        xml_file (str): 解析するXMLファイルのパス。
        columns_to_extract (list): 抽出したい属性名のリスト。

    Returns:
        pd.DataFrame: 抽出したデータを含むDataFrame。
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    trip_data = []
    for trip in root.findall('tripinfo'):
        data = {col: trip.get(col) for col in columns_to_extract}
        trip_data.append(data)
        
    return pd.DataFrame(trip_data)

# --- メイン処理 ---

# 1. ファイルパスの設定
file_step1 = '250930/data/tripinfo_0611.xml'
file_step4 = '250930/data/tripinfo_0916_backbrtuser_laketown.xml'
output_csv = '250930/data/tripinfo_BRT.csv'

# 2. 抽出するカラムの定義
# step1からは静的な情報（vTypeなど）も抽出
columns_step1 = [
    'id', 'departLane', 'arrivalLane', 'vType',
    'duration', 'routeLength', 'waitingTime', 'stopTime', 'timeLoss'
]
# step4からは変動する可能性のある性能指標のみ抽出
columns_step4 = [
    'id', 'duration', 'routeLength', 'waitingTime', 'stopTime', 'timeLoss'
]

print(f"'{file_step1}' を読み込んでいます...")
df_step1 = parse_tripinfo(file_step1, columns_step1)

print(f"'{file_step4}' を読み込んでいます...")
df_step4 = parse_tripinfo(file_step4, columns_step4)

# 3. カラム名の変更（マージ時の重複を避けるため）
df_step1 = df_step1.rename(columns={
    'duration': 'step1_duration',
    'routeLength': 'step1_routeLength',
    'waitingTime': 'step1_waitingTime',
    'stopTime': 'step1_stopTime',
    'timeLoss': 'step1_timeLoss'
})

# ご要望のカラム名 'step2_...' は、入力ファイル名に合わせて 'step4_...' としています。
df_step4 = df_step4.rename(columns={
    'duration': 'step4_duration',
    'routeLength': 'step4_routeLength',
    'waitingTime': 'step4_waitingTime',
    'stopTime': 'step4_stopTime',
    'timeLoss': 'step4_timeLoss'
})

# 4. データのマージ
# 'how="inner"' を指定することで、両方のファイルに存在するtripIDのみを対象とする
print("2つのデータをtripIDでマージしています...")
merged_df = pd.merge(df_step1, df_step4, on='id', how='inner')

# 5. 最終的なカラムの順序を定義
final_columns = [
    'id', 'departLane', 'arrivalLane', 'vType',
    'step1_duration', 'step1_routeLength', 'step1_waitingTime', 'step1_stopTime', 'step1_timeLoss',
    'step4_duration', 'step4_routeLength', 'step4_waitingTime', 'step4_stopTime', 'step4_timeLoss'
]

# カラムの順序を並び替え
final_df = merged_df[final_columns]

# 6. CSVファイルとして出力
final_df.to_csv(output_csv, index=False)

print(f"\n処理が完了しました。結果を '{output_csv}' に保存しました。")
print(f"共通のtripIDを持つトリップの数: {len(final_df)}")