# rou生成の手順（改訂版）

**編集前ファイル保管場所:** [Google Drive](https://drive.google.com/drive/u/2/folders/1RL4n9RG5QDTQh-r78zjbPrOh8-7WM4Cx)

## 用語解説

* **rou.xml**
    * シミュレーション中に登場する車両のルート情報を定義するファイル。
* **add.xml**
    * 信号、検出器、バス停といった追加の交通施設を定義するファイル。
* **net.xml**
    * シミュレーションの土台となる道路ネットワーク全体を定義する中心的なファイル。
    * `nodes.xml`, `edges.xml`, `types.xml`といったファイルを`netconvert`ツールで変換しても作成可能です。
    * 今回使用される`net.xml`および`edg.xml`：[Google Drive](https://drive.google.com/drive/folders/1pMsTh9wPBD8Ophep2aUdwzGCEwFacNHX?usp=drive_link)

---

## 1. トリップの抽出

ETCデータから車両のトリップ情報（出発地、目的地など）を抽出します。

**コマンド:**
```bash
python3 extract.py
```
**備考:**
* スクリプト内のETCデータファイルのパスと、出力したいCSVファイル名を適宜変更してください。
* 既存の`trips.csv`を流用する場合、この手順は不要です。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ETCプローブデータ（元データ） |
| **Output** | `filename_trips.csv`（抽出されたトリップ情報） |

---

## 2. マップマッチングとrouファイルの生成

抽出したトリップ情報を、シミュレーションの道路ネットワーク上に割り当て（マップマッチング）、基本的な`rou.xml`ファイルを生成します。

**コマンド:**
```bash
python3 make_matching_share.py
```
**備考:**
* `vType`（車両タイプ）の判別もこのステップで行います。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ・`filename_trips.csv` （ステップ1で生成）<br>・`filename.edg.xml` （道路ネットワークのエッジ情報） |
| **Output** | ・`filename.rou.xml` （マップマッチング後のルートファイル）<br>・`filename_matched.csv` （マッチング結果のエッジ情報が追加されたCSV） |

---

## 3. duarouterによる経路探索 (任意)

マップマッチングで得られた出発地・目的地に基づき、SUMOで実際の走行経路を探索させます。

**コマンド例:**
```bash
duarouter -n master_fotResearch.net.xml -r rou_9days_1208_nodes.rou.xml --routing-algorithm astar --routing-threads 30 -o out_nodes.xml --ignore-errors true --route-length true --exit-times true --junction-taz true
```
**備考:**
* `-n`, `-r`, `-o` のファイル名はご自身の環境に合わせて変更してください。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ・`filename.net.xml` （ネットワークファイル）<br>・`filename.rou.xml` （ステップ2で生成） |
| **Output** | ・`filename_out_nodes.xml` （実際の経路長などの情報が付与されたファイル） |

---

## 4. 不適切なトリップの削除 (任意)

短すぎる、または経路探索に失敗したトリップをデータセットから削除し、品質を向上させます。

**コマンド:**
```bash
python3 drop_bad_rou_v2.py
```
**備考:**
* _v2を利用すると、普及率を書き換えることで、自動で1日あたりの交通量を計算して出力してくれます。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ・`filename_matched_csv`（ステップ2で生成したマッチンング後のcsvファイル）<br>・`out_nodes.xml` （ステップ3で生成）|
| **Output** | ・`filename_dropped_v2.rou.xml` （不適切トリップが削除されたルートファイル）|

---

## 5. 追加rouファイルのための準備

シミュレーションに背景交通を追加するため、ランダムな出発地・目的地を持つトリップを新たに生成します。

**コマンド:**
```bash
python3 add_new_rou_1.py
```

| | ファイル/データ |
| :--- | :--- |
| **Input** | `filename.edg.xml` （道路ネットワークのエッジ情報） |
| **Output**| `filename_additional_trips.rou.xml` （追加分のトリップ情報） |

---

## 6. 追加rouファイルの経路探索

ステップ5で生成した追加トリップに対して`duarouter`を実行し、経路が存在するものだけを抽出します。

**コマンド:**
* ステップ3と同様の`duarouter`コマンドを実行します。入力の`.rou.xml`をステップ5で生成したものに変更してください。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ・`filename.net.xml`<br>・`filename_additional_trips.rou.xml` （ステップ5で生成） |
| **Output**| ・`filename_additional_out_nodes.xml` （経路探索後の追加トリップ情報）|

---

## 7. 最終的なrouファイルの結合

元のトリップと追加分のトリップを結合し、最終的な`rou.xml`を生成します。

**コマンド:**
```bash
python3 add_new_rou_2_v2.py
```
**備考:**
* _v1ではスクリプト内で、追加したいトリップ数を指定します。
* _v2を利用すると、普及率を書き換えることで、自動で1日あたりの交通量を計算して出力してくれます。

| | ファイル/データ |
| :--- | :--- |
| **Input** | ・`filename_matched_csv`（ステップ2で生成したマッチンング後のcsvファイル）<br>・`filename_out_nodes.xml` （ステップ3で生成）<br>・`filename_additional_out_nodes.xml` （ステップ6で生成） |
| **Output**| ・`filename_added_v2.rou.xml` （全てのトリップが含まれた最終的なルートファイル）|
