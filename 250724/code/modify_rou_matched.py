import os

# --- 設定項目 ---
# XMLファイルのパスを指定
file_path = '250724/data/sunday_BRT_matched.rou.xml'

# 置換する文字列のペアを辞書で定義
# '置換前の文字列': '置換後の文字列'
replacements = {
    'to="J305_genbus"': 'toJunction="1388616614"',
    'to="J306_genbus"': 'toJunction="1810854435"'
}
# --- 設定はここまで ---

def replace_in_file(path, rep_dict):
    """
    ファイル内の指定された文字列を置換して上書き保存する関数
    """
    # ファイルの存在チェック
    if not os.path.exists(path):
        print(f"エラー: ファイルが見つかりません。パスを確認してください: {path}")
        return

    try:
        # ファイルを読み込みモードで開く
        with open(path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        
        print(f"ファイルを読み込みました: {path}")

        # 文字列を置換
        original_content = file_content
        for old, new in rep_dict.items():
            file_content = file_content.replace(old, new)
        
        # もし内容に変更がなければ何もしない
        if original_content == file_content:
            print("置換対象の文字列が見つからなかったため、ファイルは変更されませんでした。")
            return

        # 同じファイルに書き込みモードで開いて、置換後の内容を書き込む
        with open(path, 'w', encoding='utf-8') as file:
            file.write(file_content)
        
        print(f"置換処理が完了し、ファイルを上書き保存しました: {path}")

    except Exception as e:
        print(f"処理中にエラーが発生しました: {e}")

# 関数を実行
if __name__ == "__main__":
    replace_in_file(file_path, replacements)