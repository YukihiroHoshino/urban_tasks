import xml.etree.ElementTree as ET
import random
import os
from collections import defaultdict
import copy

# =============================================================================
# 1. 入力・出力ファイルとシナリオの定義
# =============================================================================

# ベースとなる交通流のルートファイル
BASE_ROU_FILE = '250724/data/sunday_BRT_dropped.rou.xml'
# サンプリング対象となる、Junction指定のトリップ定義プール
ADDITIONAL_TRIP_POOL_FILE = '250724/data/yashio_additional_trips_pool_IC.rou.xml'
# duarouterで経路計算が成功したトリップのIDリストを取得するためのファイル
VALIDATED_OUTPUT_FILE = '250724/data/yashio_additional_out_nodes.xml'
# 出力ファイルのベースパス
FINAL_ROU_FILE_PATH = '250724/data/sunday_yashio_added.rou.xml'

# --- シナリオごとの追加トリップ定義 ---
# add_rou_list_1: [from_junction, to_junction, sample_count]
add_rou_list_1 = [
    ["128185343", "Anywhere", 90], ["1231325634#1", "Anywhere", 90],
    ["Anywhere", "128185343", 90], ["Anywhere", "1231325634#1", 90],
    ["314943854#8", "Anywhere", 260], ["Anywhere", "314943854#8", 260],
    ["-314943854#4", "Anywhere", 80], ["314943854#4.70", "Anywhere", 80],
    ["Anywhere", "-314943854#4", 80], ["Anywhere", "314943854#4.70", 80],
    ["628774981#1", "Anywhere", 120], ["Anywhere", "628774981#1", 120],
    ["-732836013#5", "Anywhere", 280], ["Anywhere", "-732836013#5", 280]
]

# add_rou_list_2: [parking_area_id, sample_count]
add_rou_list_2_1_1 = [["pa_1_south", 1500], ["pa_1_west", 1500]]
add_rou_list_2_1_2 = [["pa_1_south", 3000], ["pa_1_west", 3000]]
add_rou_list_2_2_1 = [["pa_2_south", 1500], ["pa_2_west", 1500]]
add_rou_list_2_2_2 = [["pa_2_south", 3000], ["pa_2_west", 3000]]
add_rou_list_2_3_1 = [["pa_3_east", 3000]]
add_rou_list_2_3_2 = [["pa_3_east", 6000]]

# --- シナリオマップ ---
scenario_map = {
    2: {"truck": add_rou_list_1, "normal": add_rou_list_2_1_1},
    3: {"truck": add_rou_list_1, "normal": add_rou_list_2_1_2},
    4: {"truck": add_rou_list_1, "normal": add_rou_list_2_2_1},
    5: {"truck": add_rou_list_1, "normal": add_rou_list_2_2_2},
    6: {"truck": add_rou_list_1, "normal": add_rou_list_2_3_1},
    7: {"truck": add_rou_list_1, "normal": add_rou_list_2_3_2},
}

# =============================================================================
# 2. ヘルパー関数
# =============================================================================

def get_valid_trip_ids(validated_file: str) -> set:
    """duarouterの出力ファイルから、正常に経路付けされたトリップIDのセットを返す"""
    print(f"Reading valid trip IDs from '{validated_file}'...")
    try:
        tree = ET.parse(validated_file)
        root = tree.getroot()
        valid_ids = {elem.get('id') for elem in root.findall('.//trip') + root.findall('.//vehicle')}
        print(f"Found {len(valid_ids)} valid trip IDs.")
        return valid_ids
    except FileNotFoundError:
        print(f"Error: Validated trips file not found at '{validated_file}'")
        return set()
    except ET.ParseError:
        print(f"Error: Could not parse XML file '{validated_file}'")
        return set()

def load_and_categorize_trip_pool(pool_file: str, valid_ids: set) -> dict:
    """トリッププールファイルを読み込み、有効なトリップをfrom, to, parkingAreaで分類する"""
    print(f"Loading and categorizing trips from '{pool_file}'...")
    categorized_trips = {
        'by_from': defaultdict(list),
        'by_to': defaultdict(list),
        'by_pa': defaultdict(list)
    }
    try:
        tree = ET.parse(pool_file)
        root = tree.getroot()
        
        count = 0
        for trip in root.findall('.//trip'):
            trip_id = trip.get('id')
            if trip_id in valid_ids:
                from_loc = trip.get('from')
                if from_loc:
                    categorized_trips['by_from'][from_loc].append(trip)
                to_loc = trip.get('to')
                if to_loc:
                    categorized_trips['by_to'][to_loc].append(trip)
                stop_elem = trip.find('stop')
                if stop_elem is not None:
                    pa_id = stop_elem.get('parkingArea')
                    if pa_id:
                        categorized_trips['by_pa'][pa_id].append(trip)
                count += 1
        print(f"Successfully loaded and categorized {count} valid trips.")
        return categorized_trips
    except FileNotFoundError:
        print(f"Error: Trip pool file not found at '{pool_file}'")
        return {}
    except ET.ParseError:
        print(f"Error: Could not parse XML file '{pool_file}'")
        return {}

# ▼▼▼【新規追加】トリップごとのランダム属性を事前計算する関数 ▼▼▼
def precompute_random_attributes(categorized_pool: dict) -> dict:
    """
    全ての有効なトリップに対し、IDに基づいた固定のランダム属性を事前計算する。
    これにより、どのシナリオで選択されても同じdepart値やduration値が使われる。
    """
    print("Pre-computing random attributes for all valid trips...")
    trip_attributes = {}
    
    # カテゴライズされたプールから一意なトリップ要素を収集
    all_unique_trips = {}
    for category in categorized_pool.values():
        for trip_list in category.values():
            for trip in trip_list:
                trip_id = trip.get('id')
                if trip_id not in all_unique_trips:
                    all_unique_trips[trip_id] = trip

    for trip_id, trip_elem in all_unique_trips.items():
        # トリップIDのハッシュ値をシードとして使い、ID固有の乱数を生成
        temp_seed = hash(trip_id)
        random.seed(temp_seed)

        # このトリップIDに対するランダム属性をすべて生成
        truck_depart = random.randint(0, 86399)
        normal_depart = random.randint(32400, 61200)
        
        normal_duration = None
        if trip_elem.find('stop') is not None:
            normal_duration = random.randint(5400, 7200)

        trip_attributes[trip_id] = {
            'truck_depart': truck_depart,
            'normal_depart': normal_depart,
            'normal_duration': normal_duration
        }
    
    print(f"Pre-computed attributes for {len(trip_attributes)} unique trips.")
    return trip_attributes

def sample_trips(categorized_pool: dict, rules: list) -> list:
    """指定されたルールリストに基づいてトリップをサンプリングする"""
    sampled_elements = []
    
    for rule in rules:
        candidates = []
        if len(rule) == 3:
            from_loc, to_loc, count = rule
            if from_loc != "Anywhere":
                candidates = categorized_pool['by_from'].get(from_loc, [])
            elif to_loc != "Anywhere":
                candidates = categorized_pool['by_to'].get(to_loc, [])
        elif len(rule) == 2:
            pa_id, count = rule
            candidates = categorized_pool['by_pa'].get(pa_id, [])
        else:
            continue
            
        if not candidates:
            print(f"Warning: No valid trips found for rule: {rule}. Skipping.")
            continue
        
        num_to_sample = min(count, len(candidates))
        sampled_list = random.sample(candidates, num_to_sample)
        sampled_elements.extend(copy.deepcopy(trip) for trip in sampled_list)
        
    return sampled_elements

def generate_output_path(base_path: str, scenario_num: int) -> str:
    """シナリオ番号に基づいて出力ファイルパスを生成する"""
    directory = os.path.dirname(base_path)
    filename, ext = os.path.splitext(os.path.basename(base_path))
    if ext.lower() == '.xml':
        filename, ext2 = os.path.splitext(filename)
        ext = ext2 + ext
    new_filename = f"{filename}_scenario_{scenario_num}{ext}"
    return os.path.join(directory, new_filename)

# =============================================================================
# 3. メイン処理
# =============================================================================

def main():
    """メイン実行関数"""
    output_dir = os.path.dirname(FINAL_ROU_FILE_PATH)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    valid_ids = get_valid_trip_ids(VALIDATED_OUTPUT_FILE)
    if not valid_ids:
        print("Could not retrieve valid trip IDs. Aborting.")
        return

    categorized_trip_pool = load_and_categorize_trip_pool(ADDITIONAL_TRIP_POOL_FILE, valid_ids)
    if not categorized_trip_pool:
        print("Could not load the trip pool. Aborting.")
        return

    # ▼▼▼【修正点】全トリップのランダム属性を事前に計算 ▼▼▼
    trip_attributes = precompute_random_attributes(categorized_trip_pool)
        
    for scenario_num, scenario_details in scenario_map.items():
        print(f"\n--- Processing Scenario {scenario_num} ---")
        random.seed(0)
        
        try:
            base_tree = ET.parse(BASE_ROU_FILE)
            base_root = base_tree.getroot()
        except FileNotFoundError:
            print(f"Error: Base route file '{BASE_ROU_FILE}' not found. Skipping scenario.")
            continue
        except ET.ParseError:
            print(f"Error: Could not parse base XML file '{BASE_ROU_FILE}'. Skipping scenario.")
            continue

        all_newly_sampled_trips = []
        for vehicle_type, rules in scenario_details.items():
            print(f"Sampling trips for '{vehicle_type}'...")
            newly_sampled_trips = sample_trips(categorized_trip_pool, rules)
            
            for trip_element in newly_sampled_trips:
                original_id = trip_element.get('id')
                
                # ▼▼▼【修正点】事前計算した辞書から値を参照する ▼▼▼
                attributes = trip_attributes.get(original_id)
                if not attributes:
                    print(f"Warning: Could not find pre-computed attributes for trip ID {original_id}. Skipping modification.")
                    continue

                # 1. IDの接頭辞を変更
                if original_id:
                    new_id = original_id.replace('pool_', 'add_', 1)
                    trip_element.set('id', new_id)
                
                # 2. vehicle_typeに応じて出発時刻を設定
                if vehicle_type == "truck":
                    depart_time = attributes['truck_depart']
                elif vehicle_type == "normal":
                    depart_time = attributes['normal_depart']
                else:
                    depart_time = 0
                trip_element.set('depart', str(depart_time))

                # 3. "normal"トリップの場合、停車時間を設定
                if vehicle_type == "normal":
                    stop_elem = trip_element.find('stop')
                    if stop_elem is not None and attributes['normal_duration'] is not None:
                        stop_elem.set('duration', str(attributes['normal_duration']))

            all_newly_sampled_trips.extend(newly_sampled_trips)
            print(f"Added and modified {len(newly_sampled_trips)} trips for '{vehicle_type}'.")
        
        for trip in all_newly_sampled_trips:
            base_root.append(trip)
        
        print("Sorting all elements by departure time...")
        
        def get_sort_key(element):
            depart_time_str = element.get('depart')
            if depart_time_str is None: return -1.0
            try: return float(depart_time_str)
            except (ValueError, TypeError): return float('inf')

        sorted_children = sorted(list(base_root), key=get_sort_key)
        
        base_root.clear()
        base_root.extend(sorted_children)
        
        output_file_path = generate_output_path(FINAL_ROU_FILE_PATH, scenario_num)
        base_tree.write(output_file_path, encoding='utf-8', xml_declaration=True)
        
        print(f"Total {len(all_newly_sampled_trips)} trips were processed.")
        print(f"Scenario {scenario_num} route file sorted and saved to: '{output_file_path}'")

    print("\nAll scenarios processed successfully.")

if __name__ == "__main__":
    main()