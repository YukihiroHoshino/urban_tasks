# rouの生成方法の共有（改訂版）
ファイルの場所：https://drive.google.com/drive/u/2/folders/1RL4n9RG5QDTQh-r78zjbPrOh8-7WM4Cx

1. tripの抽出
python3 extract.py
ETCデータのファイルの場所とoutputとなるcsvのファイル名だけ変更する
ファイルをダウンロードするのは大変だと思うので、既存のデータで良いならtrips.csvの結果を流用すれば良い

2. rouの生成
python3 make_matching_share.py
edg.xmlと上で作ったcsvのファイル名だけ変更する
outputはマッチング結果のcsvとrou

3. duarouter (任意)
duarouter -n master_fotResearch.net.xml -r rou_9days_1208_nodes.rou.xml --routing-algorithm astar --routing-threads 30 -o out_nodes.xml --ignore-errors true --route-length true --exit-times true --junction-taz true
適宜ファイル名は変更

4. 不適切なトリップを削除 (任意)
python3 drop_bad_rou.py
適宜ファイル名は変更

5. rou追加のための準備
python3 add_new_rou_1.py
ランダムな出発地・目的地へのトリップを作る

6. duarouter
で作ったrouにduarouterをかけて、経路が存在するものだけを抽出する

7. 最後
python3 add_new_rou_2.py
適切な数を指定してrouを追加する