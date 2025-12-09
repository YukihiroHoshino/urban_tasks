import xml.etree.ElementTree as ET
import random
import os

# --- 設定項目 ---
# 編集したいnetファイルの名前
INPUT_NET_FILE = '250724/data/master_forResearch_fixed_bukai_step4_truck_jp.net.xml'

# 変更を保存する新しいnetファイルの名前
OUTPUT_NET_FILE = '250724/data/master_forResearch_fixed_bukai_step4_truck_jp_edit.net.xml'

# offsetの最小値と最大値
MIN_OFFSET = 0
MAX_OFFSET = 89

# 乱数のシード値（0に固定）
RANDOM_SEED = 0
# ----------------

def modify_tlLogic_offsets(input_file, output_file):
    """
    SUMOのnetファイルを読み込み、全てのtlLogicタグのoffset属性を
    ランダムな値に書き換えて新しいファイルに保存します。
    """
    # 乱数シードを固定
    random.seed(RANDOM_SEED)

    # XMLファイルの存在チェック
    if not os.path.exists(input_file):
        print(f"エラー: ファイル '{input_file}' が見つかりません。")
        return

    try:
        # XMLファイルをパース
        tree = ET.parse(input_file)
        root = tree.getroot()

        # <tlLogic> タグを全て検索
        modified_count = 0
        for tl_logic in root.findall('tlLogic'):
            # 0から89の範囲でランダムな整数を生成
            new_offset = random.randint(MIN_OFFSET, MAX_OFFSET)
            
            # offset属性を新しい値に設定
            tl_logic.set('offset', str(new_offset))
            modified_count += 1

        # 変更を新しいファイルに書き込む
        tree.write(output_file, encoding='UTF-8', xml_declaration=True)

        print(f"処理が完了しました。")
        print(f"{modified_count}個の信号オフセットを更新し、'{output_file}' に保存しました。")

    except ET.ParseError:
        print(f"エラー: ファイル '{input_file}' のXMLパースに失敗しました。")
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")


if __name__ == '__main__':
    # INPUT_NET_FILEがデフォルト値のままなら注意を促す
    if INPUT_NET_FILE == 'your_net_file.net.xml':
        print("注意: スクリプト内の 'INPUT_NET_FILE' を編集対象のファイル名に変更してください。")
    else:
        modify_tlLogic_offsets(INPUT_NET_FILE, OUTPUT_NET_FILE)