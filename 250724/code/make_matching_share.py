import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from tqdm import tqdm
import sys
from sklearn.neighbors import KDTree
sys.setrecursionlimit(20000000)

class ETCDataProcessor:
    def __init__(self, trips_df, edg_file_path, net_file_path, csv_file_path):
        self.trips_df = trips_df
        self.edg_file_path = edg_file_path
        self.net_file_path = net_file_path
        self.csv_file_path = csv_file_path
        self.edges_df = None
        self.nodes_df = None
        self.clusters = None
        self.nodes_highway_from_df = None
        self.nodes_highway_to_df = None
        self.nodes_not_highway_from_df = None
        self.nodes_not_highway_to_df = None
        

    def calc_xy(self, phi_deg, lambda_deg, phi0_deg, lambda0_deg):
        """ 緯度経度を平面直角座標に変換する
        - input:
            (phi_deg, lambda_deg): 変換したい緯度・経度[度]（分・秒でなく小数であることに注意）
            (phi0_deg, lambda0_deg): 平面直角座標系原点の緯度・経度[度]（分・秒でなく小数であることに注意）
        - output:
            x: 変換後の平面直角座標[m]
            y: 変換後の平面直角座標[m]
        """
        # 緯度経度・平面直角座標系原点をラジアンに直す
        phi_rad = np.deg2rad(phi_deg)
        lambda_rad = np.deg2rad(lambda_deg)
        phi0_rad = np.deg2rad(phi0_deg)
        lambda0_rad = np.deg2rad(lambda0_deg)

        # 補助関数
        def A_array(n):
            A0 = 1 + (n**2)/4. + (n**4)/64.
            A1 = -     (3./2)*( n - (n**3)/8. - (n**5)/64. ) 
            A2 =     (15./16)*( n**2 - (n**4)/4. )
            A3 = -   (35./48)*( n**3 - (5./16)*(n**5) )
            A4 =   (315./512)*( n**4 )
            A5 = -(693./1280)*( n**5 )
            return np.array([A0, A1, A2, A3, A4, A5])

        def alpha_array(n):
            a0 = np.nan # dummy
            a1 = (1./2)*n - (2./3)*(n**2) + (5./16)*(n**3) + (41./180)*(n**4) - (127./288)*(n**5)
            a2 = (13./48)*(n**2) - (3./5)*(n**3) + (557./1440)*(n**4) + (281./630)*(n**5)
            a3 = (61./240)*(n**3) - (103./140)*(n**4) + (15061./26880)*(n**5)
            a4 = (49561./161280)*(n**4) - (179./168)*(n**5)
            a5 = (34729./80640)*(n**5)
            return np.array([a0, a1, a2, a3, a4, a5])

        # 定数 (a, F: 世界測地系-測地基準系1980（GRS80）楕円体)
        m0 = 0.9999 
        a = 6378137.
        F = 298.257222101

        # (1) n, A_i, alpha_iの計算
        n = 1. / (2*F - 1)
        A_array = A_array(n)
        alpha_array = alpha_array(n)

        # (2), S, Aの計算
        A_ = ( (m0*a)/(1.+n) )*A_array[0] # [m]
        S_ = ( (m0*a)/(1.+n) )*( A_array[0]*phi0_rad + np.dot(A_array[1:], np.sin(2*phi0_rad*np.arange(1,6))) ) # [m]

        # (3) lambda_c, lambda_sの計算
        lambda_c = np.cos(lambda_rad - lambda0_rad)
        lambda_s = np.sin(lambda_rad - lambda0_rad)

        # (4) t, t_の計算
        t = np.sinh( np.arctanh(np.sin(phi_rad)) - ((2*np.sqrt(n)) / (1+n))*np.arctanh(((2*np.sqrt(n)) / (1+n)) * np.sin(phi_rad)) )
        t_ = np.sqrt(1 + t*t)

        # (5) xi', eta'の計算
        xi2  = np.arctan(t / lambda_c) # [rad]
        eta2 = np.arctanh(lambda_s / t_)

        # (6) x, yの計算
        x = A_ * (xi2 + np.sum(np.multiply(alpha_array[1:],
                                        np.multiply(np.sin(2*xi2*np.arange(1,6)),
                                                    np.cosh(2*eta2*np.arange(1,6)))))) - S_ # [m]
        y = A_ * (eta2 + np.sum(np.multiply(alpha_array[1:],
                                            np.multiply(np.cos(2*xi2*np.arange(1,6)),
                                                        np.sinh(2*eta2*np.arange(1,6)))))) # [m]
        # return
        return x, y # [m]


    def prepare_matching_candidates(self):
        edg_xml = ET.parse(self.edg_file_path).getroot()
        edge_list = []
        highway_from = {}
        highway_to = {}
        not_highway_from = {}
        not_highway_to = {}

        for child in edg_xml:
            if child.tag == 'edge' and 'shape' in child.attrib:
                shapes = [shape.split(',') for shape in child.attrib['shape'].split(' ')]
                if child.attrib['type'] in ['highway.motorway', 'highway.trunk', 'highway.primary', 'highway.secondary', 'highway.tertiary', 'highway.unclassified']:
                    highway = 1 if child.attrib['type'] == 'highway.motorway' else 0
                    edge_list.append((child.attrib['id'], shapes[0][0], shapes[0][1], shapes[-1][0], shapes[-1][1], highway))
                    if highway == 1:
                        highway_from[child.attrib['from']] = [child.attrib['from'] + 'N', shapes[0][0], shapes[0][1]]
                        highway_to[child.attrib['to']] = [child.attrib['to']+'N', shapes[-1][0], shapes[-1][1]]
                    else:
                        not_highway_from[child.attrib['from']] = [child.attrib['from']+'N', shapes[0][0], shapes[0][1]]
                        not_highway_to[child.attrib['to']] = [child.attrib['to']+'N', shapes[-1][0], shapes[-1][1]]


        self.nodes_highway_from_df = pd.DataFrame(list(highway_from.values()), columns=['edge_id', 'depart_x', 'depart_y'])
        self.nodes_highway_to_df = pd.DataFrame(list(highway_to.values()), columns=['edge_id', 'dest_x', 'dest_y'])
        self.nodes_not_highway_from_df = pd.DataFrame(list(not_highway_from.values()), columns=['edge_id', 'depart_x', 'depart_y'])
        self.nodes_not_highway_to_df = pd.DataFrame(list(not_highway_to.values()), columns=['edge_id', 'dest_x', 'dest_y'])

        #それぞれfroatに変換
        self.nodes_highway_from_df['depart_x'] = self.nodes_highway_from_df['depart_x'].astype(float)
        self.nodes_highway_from_df['depart_y'] = self.nodes_highway_from_df['depart_y'].astype(float)
        self.nodes_highway_to_df['dest_x'] = self.nodes_highway_to_df['dest_x'].astype(float)
        self.nodes_highway_to_df['dest_y'] = self.nodes_highway_to_df['dest_y'].astype(float)
        self.nodes_not_highway_from_df['depart_x'] = self.nodes_not_highway_from_df['depart_x'].astype(float)
        self.nodes_not_highway_from_df['depart_y'] = self.nodes_not_highway_from_df['depart_y'].astype(float)
        self.nodes_not_highway_to_df['dest_x'] = self.nodes_not_highway_to_df['dest_x'].astype(float)
        self.nodes_not_highway_to_df['dest_y'] = self.nodes_not_highway_to_df['dest_y'].astype(float)



    def map_matching(self):
        edges_cluster_depart_highway = []
        edges_cluster_name_depart_highway = []
        edges_cluster_dest_highway = []
        edges_cluster_name_dest_highway = []
        for index, row in self.nodes_highway_from_df.iterrows():
            x, y = self.calc_xy(row['depart_y'], row['depart_x'], 35.876124,139.821685)
            edges_cluster_depart_highway.append([x, y])
            edges_cluster_name_depart_highway.append(row['edge_id'])

        for index, row in self.nodes_highway_to_df.iterrows():
            x, y = self.calc_xy(row['dest_y'], row['dest_x'], 35.876124,139.821685)
            edges_cluster_dest_highway.append([x, y])
            edges_cluster_name_dest_highway.append(row['edge_id'])

        edges_cluster_kdtree_depart_highway = KDTree(edges_cluster_depart_highway)
        edges_cluster_kdtree_dest_highway = KDTree(edges_cluster_dest_highway)

        edges_cluster_depart_not_highway = []
        edges_cluster_name_depart_not_highway = []
        edges_cluster_dest_not_highway = []
        edges_cluster_name_dest_not_highway = []
        for index, row in self.nodes_not_highway_from_df.iterrows():
            x, y = self.calc_xy(row['depart_y'], row['depart_x'], 35.876124,139.821685)
            edges_cluster_depart_not_highway.append([x, y])
            edges_cluster_name_depart_not_highway.append(row['edge_id'])
        
        for index, row in self.nodes_not_highway_to_df.iterrows():
            x, y = self.calc_xy(row['dest_y'], row['dest_x'], 35.876124,139.821685)
            edges_cluster_dest_not_highway.append([x, y])
            edges_cluster_name_dest_not_highway.append(row['edge_id'])

        edges_cluster_kdtree_depart_not_highway = KDTree(edges_cluster_depart_not_highway)
        edges_cluster_kdtree_dest_not_highway = KDTree(edges_cluster_dest_not_highway)
        
        closest_edges_origin = []
        closest_edges_destination = []
        cluster_number = []
        all_count = len(self.trips_df)

        for index, row in tqdm(self.trips_df.iterrows(), total=all_count):

            x, y = self.calc_xy(row['緯度_origin'], row['経度_origin'], 35.876124,139.821685)
            origin = [x, y]
            x, y = self.calc_xy(row['緯度_destination'], row['経度_destination'], 35.876124,139.821685)
            destination = [x, y]
            if row["起点の道路種別コード"] in [0,1]:
                dist_origin, ind_origin = edges_cluster_kdtree_depart_highway.query([origin], k=1)
                ind_origin_0 = int(ind_origin.item(0))
                closest_edges_origin.append(edges_cluster_name_depart_highway[ind_origin_0])
            else:
                dist_origin, ind_origin = edges_cluster_kdtree_depart_not_highway.query([origin], k=1)
                ind_origin_0 = int(ind_origin.item(0))
                closest_edges_origin.append(edges_cluster_name_depart_not_highway[ind_origin_0])
            if row["終点の道路種別コード"] in [0,1]:
                dist_destination, ind_destination = edges_cluster_kdtree_dest_highway.query([destination], k=1)
                ind_destination_0 = int(ind_destination.item(0))
                closest_edges_destination.append(edges_cluster_name_dest_highway[ind_destination_0])
            else:
                dist_destination, ind_destination = edges_cluster_kdtree_dest_not_highway.query([destination], k=1)
                ind_destination_0 = int(ind_destination.item(0))
                closest_edges_destination.append(edges_cluster_name_dest_not_highway[ind_destination_0])

        self.trips_df['edge_id_origin'] = closest_edges_origin
        self.trips_df['edge_id_destination'] = closest_edges_destination

        # tripinfoとETC2.0の比較のためidを振り直すß
        rou_id = []
        for i in range(len(self.trips_df)):
            rou_id.append(str(self.trips_df['運行日'].iloc[i]) + '_' + str(self.trips_df['運行ID1'].iloc[i]) + '_' + str(self.trips_df['トリップ番号'].iloc[i]))
        self.trips_df['rou_id'] = rou_id

        # CSVファイルに保存
        self.trips_df.to_csv(csv_file_path, index=False)


    def format_output(self, rou_file_path):
        rou_root = ET.Element('routes')

        trips_temp = []
        # ★★★ 変更点1: trips_tempに自動車の種別を追加 ★★★
        for i in range(len(self.trips_df)):
            id_ = self.trips_df['rou_id'].iloc[i]
            from_ = self.trips_df['edge_id_origin'].iloc[i]
            to_ = self.trips_df['edge_id_destination'].iloc[i]
            depart_at_raw_ = str(self.trips_df['トリップの起点時刻'].values[i])
            depart_at_ = int(depart_at_raw_[8:10])*3600 + int(depart_at_raw_[10:12])*60 + int(depart_at_raw_[12:14])
            # 自動車の種別を取得
            car_type_ = self.trips_df['自動車の種別'].iloc[i]
            trips_temp.append([id_, from_, to_, depart_at_, car_type_])


        trips_temp.sort(key=lambda x: x[3])
        for l in trips_temp:
            l[3] = str(int(l[3]))

        def indent(elem, level=0):
            i = '\n' + level*'  '
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + '  '
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for elem in elem:
                    indent(elem, level+1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i
        
        # ★★★ 変更点2: XML生成時にvType属性を追加 ★★★
        for i, single_demand in enumerate(trips_temp):
            trip = ET.SubElement(rou_root, 'trip')
            trip.set('id', f't_{single_demand[0]}')

            # 自動車の種別に応じてvTypeを設定
            car_type = single_demand[4]
            if car_type == 1:
                trip.set('type', 'truck')
            
            trip.set('depart', str(single_demand[3]))
            if single_demand[1][-1] == 'N':
                trip.set('fromJunction', single_demand[1][:-1])
            else:
                trip.set('from', single_demand[1])
            if single_demand[2][-1] == 'N':
                trip.set('toJunction', single_demand[2][:-1])
            else:
                trip.set('to', single_demand[2])

            # 自動車の種別に応じてvTypeを設定
            car_type = single_demand[4]
            if car_type == 1:
                trip.set('type', 'truck')
            elif car_type == 0 or car_type >= 2:
                continue

        rou_tree = ET.ElementTree(rou_root)

        with open(rou_file_path, 'w', encoding='utf-8') as file:
            indent(rou_root)
            rou_tree.write(file, encoding='unicode', xml_declaration=True)

    def process(self, rou_file_path):
        self.prepare_matching_candidates()
        self.map_matching()
        self.format_output(rou_file_path)
    
    def process_from_csv(self, rou_file_path):
        self.format_output(rou_file_path)

def sample_random_trips(n, trips_df_csv="./trips_df.csv", random_trips_df_csv="random_trips_df.csv"):
    # CSVファイルの総行数を取得
    total_rows = sum(1 for _ in open(trips_df_csv)) - 1  # ヘッダー行を除く

    # n が総行数よりも大きい場合、総行数に設定
    n = min(n, total_rows)

    # ランダムな行インデックスを生成
    random_indices = np.random.choice(total_rows, size=n, replace=False)

    # ランダムに選択された行を読み込む
    random_trips_df = pd.read_csv(trips_df_csv, skiprows=lambda x: x != 0 and x-1 not in random_indices)

    # 結果をCSVファイルに保存
    random_trips_df.to_csv(random_trips_df_csv, index=False)

    return random_trips_df

# # 使用例
# random_df = sample_random_trips(200000)
# print(random_df.head())

# 使用例
trips_df = pd.read_csv("250724/data/example_trips.csv")
edg_file_path = "250724/data/edge_BRT.edg.xml"
net_file_path = "250724/data/master_forResearch_fixed_genBRT_truck.net.xml"

rou_file_path = "250724/data/example_matched.rou.xml"
csv_file_path = "250724/data/example_matched.csv"

processor = ETCDataProcessor(trips_df, edg_file_path, net_file_path, csv_file_path)
processor.process(rou_file_path)


# 使用例
#trips_df = pd.read_csv("filename_trips.csv")
#edg_file_path = "./filename.edg.xml"
#net_file_path = "./filename.net.xml"

#rou_file_path = "./filename_matched.rou.xml"
#csv_file_path = "./filename_matched.csv"

#processor = ETCDataProcessor(trips_df, edg_file_path, net_file_path, csv_file_path)
#processor.process(rou_file_path)