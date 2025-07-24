# rouの生成方法の共有（改訂版）
ファイルの場所：https://drive.google.com/drive/u/2/folders/1RL4n9RG5QDTQh-r78zjbPrOh8-7WM4Cx

┌───────────────┐
│ nodes.xml     │ ←─┐
│ edges.xml     │    ├─→ netconvert → net.xml
│ types.xml     │ ←─┘

rou.xml → シミュレーション中の車両・ルート情報

add.xml → 信号、検出器、停車施設などを追加定義

net.xml（中心） ← その他はこのネットワークに基づく

1. tripの抽出
python3 extract.py
ETCデータのファイルの場所とoutputとなるcsvのファイル名だけ変更する
ファイルをダウンロードするのは大変だと思うので、既存のデータで良いならtrips.csvの結果を流用すれば良い

2. rouの生成
python3 make_matching_share.py
edg.xml上で作ったcsvのファイル名だけ変更する
input: ETC2.0から抽出したcsv, エッジ情報を示したedg.xml
output: マッチング結果のrou.xml, csv（入力したcsvにedge_id_origin, edge_id_destination, rou_idが追加）
vTypeを判別

3. duarouter (任意)
duarouter -n master_fotResearch.net.xml -r rou_9days_1208_nodes.rou.xml --routing-algorithm astar --routing-threads 30 -o out_nodes.xml --ignore-errors true --route-length true --exit-times true --junction-taz true
適宜ファイル名は変更
output: out_nodes.xml

4. 不適切なトリップを削除 (任意)
python3 drop_bad_rou.py
input: マッチング後のcsv,  duarouterで出力されるxml(tree),  マッチング後のrou
output: 不明 
適宜ファイル名は変更

5. rou追加のための準備
python3 add_new_rou_1.py
ランダムな出発地・目的地へのトリップを作る
input: エッジ情報を示したedg.xml
output: 追加分のrou.xml

6. duarouter
で作ったrouにduarouterをかけて、経路が存在するものだけを抽出する
4と同様に実行→output: out_nodes.xmlっぽいやつ

7. 最後
python3 add_new_rou_2.py
適切な数を指定してrouを追加する
input: マッチング後のcsv, マッチング後のrou.xml, duarouterで出力されるxml(tree)
output: ?