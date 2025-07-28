import pandas as pd
import os
from tqdm import tqdm
import zipfile
import tempfile

class ETCDataProcessor:
    def __init__(self, areas, dates, south, north, east, west):
        self.areas = areas
        self.dates = dates
        self.south = south
        self.north = north
        self.east = east
        self.west = west
        self.df_date = pd.DataFrame()
        self.columns = [
                        'RSU-IDコード', '受信時刻', '運行日', '運行ＩＤ1', '自動車の種別', '自動車の用途', 'GPS時刻',
                        '通し番号', 'トリップ番号', 'トリップの起点時刻', 'トリップの終点時刻', 'トリップの端点の完全性',
                        'トリップ起終点フラグ', 'タグ番号', '経度', '緯度', '蓄積条件', '道路種別コード' , '速度', '高度',
                        'マッチングフラグ', 'マッチング後経度', 'マッチング後緯度', 'DRMバージョン', '2次メッシュコード',
                        '流入ノード', '流出ノード', '流入ノードからの距離', '確定フラグ', '交通調査基本区間番号', '上り・下りコード',
                        '管理者コード', '更新日時']

    def process_data(self):
        df_date_list = []
        for date in tqdm(self.dates, desc="Processing dates"):
            month = int(str(date)[4:6])
            
            for area in tqdm(self.areas, desc="Processing areas"):
                print(f"Processing area: {area}")
                if area in [543907, 533977, 533967, 533957]:
                    #filename = f"250724/data/{month}0/OUT1-2_{area}_{date}.zip"
                    filename = f"250724/data/OUT1-2_{area}_{date}.zip"
                else:
                    #filename = f"250724/data/{month}/OUT1-2_{area}_{date}.zip"
                    filename = f"250724/data/OUT1-2_{area}_{date}.zip"
                
                if os.path.exists(filename):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        with zipfile.ZipFile(filename, 'r') as zip_ref:
                            zip_ref.extract('data.csv', tmpdir)
                        
                        csv_path = os.path.join(tmpdir, 'data.csv')
                        df = pd.read_csv(csv_path, header=None, names=self.columns, encoding='shift-jis')
                        
                        # 指定された地理的範囲内のデータのみを抽出
                        df = df[(df['経度'] > self.west) & (df['経度'] < self.east) &
                                (df['緯度'] > self.south) & (df['緯度'] < self.north)]
                        
                        def get_first_last(group):
                            return group.iloc[[0, -1]]
                        
                        grouped = df.groupby(["運行日", "運行ＩＤ1", "トリップ番号", "自動車の種別"])
                        first_last = grouped.apply(get_first_last).reset_index(drop=True)
                        
                        df_date_list.append(first_last)
                else:
                    print(f"File not found: {filename}")
                
        self.df_date = pd.concat(df_date_list)
        self.df_date = self.df_date.reset_index(drop=True)
        grouped = self.df_date.groupby(["運行日", '運行ＩＤ1', 'トリップ番号', '自動車の種別'])
        del self.df_date
        rows = []

        for name, group in tqdm(grouped, desc="処理中のトリップ", total=len(grouped)):
            group = group.sort_values(by='GPS時刻')
            first_row = group.iloc[0]
            last_row = group.iloc[-1]
        
            new_row = {
                "運行日": name[0],
                '運行ID1': name[1],
                'トリップ番号': name[2],
                '自動車の種別': name[3],
                'トリップの起点時刻': first_row['GPS時刻'],
                '起点の道路種別コード': first_row['道路種別コード'],
                '経度_origin': first_row['経度'],
                '緯度_origin': first_row['緯度'],
                'トリップの終点時刻': last_row['GPS時刻'],
                '終点の道路種別コード': last_row['道路種別コード'],
                '経度_destination': last_row['経度'],
                '緯度_destination': last_row['緯度']
            }
            rows.append(new_row)
        self.df_date = pd.DataFrame(rows)


    def save_result(self, filename="250724/data/example_trips_v2.csv"):
        self.df_date.to_csv(filename, index=False)

    def get_result(self):
        return self.df_date

# 使用例
areas = [543907]
dates = [20230605, 20230606]
south = 34.0
north = 37.0
east = 140.0
west = 138.0
#areas = [543907, 533977, 533967, 533957, 543906, 533976, 533966, 533956, 543905, 533975, 533965, 533955]
#dates = [20211003, 20211010, 20211017, 20211024, 20211031, 20211107, 20211114, 20211121, 20211128]
#south = 35.8
#north = 36.0
#east = 139.9
#west = 139.7

processor = ETCDataProcessor(areas, dates, south, north, east, west)
processor.process_data()

# 結果の表示
print(processor.get_result())

# 結果の保存
processor.save_result()