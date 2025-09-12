#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Streaming filter for large SUMO routes.xml

最適化:
- iterparse でストリーミング処理（低メモリ）
- depart 単調非減少を活用して:
  * depart < LOWER は読み捨て
  * depart が LOWER〜UPPER の間だけ書き出し
  * depart > UPPER が出たら、その後の depart 付き要素は全スキップ
- <flow> は常に残し、begin/end を LOWER/UPPER に置換して書き出し
- depart を持たない他要素（vType 等）はそのまま出力
"""

import xml.etree.ElementTree as ET
from typing import Optional, TextIO

# ===== 設定 =====
input_file = "250724/data/thursday_added_v1_scenario_2.rou.xml"             # 入力XMLファイル
output_file = "250724/data/thursday_added_v1_scenario_2_filterTime.rou.xml"   # 出力XMLファイル
LOWER = 14400                         # depart の下限
UPPER = 72000                         # depart の上限
# =================

def _to_number(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None

def _write_open_root(f: TextIO, tag: str, attrib: dict):
    # ルートの開始タグを書き出す（属性を引き継ぐ）
    attrs = "".join(f' {k}="{v}"' for k, v in attrib.items())
    f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write(f'<{tag}{attrs}>\n')

def _write_close_root(f: TextIO, tag: str):
    f.write(f'</{tag}>\n')

def _tostring(elem: ET.Element) -> str:
    # 子含めて1要素分を文字列化（末尾に改行）
    return ET.tostring(elem, encoding="unicode")

def filter_routes_streaming():
    started_in_range = False  # depart が LOWER に到達したか
    past_upper = False        # depart が UPPER を超えたあとか

    # start/end の両方を使って「直下要素」判定用の深さを管理
    context = ET.iterparse(input_file, events=("start", "end"))
    root = None
    depth = -1  # 最初の start で 0（root）、その子が 1

    with open(output_file, "w", encoding="utf-8") as out:
        for event, elem in context:
            if event == "start":
                depth += 1
                if root is None:
                    # ルート決定
                    root = elem
                    _write_open_root(out, root.tag, root.attrib)
                continue

            # event == "end" の処理
            if depth == 1:
                # 直下要素をここで処理して書き出す／捨てる
                tag_lower = elem.tag.lower()

                if tag_lower == "flow":
                    # flow は常に残し、begin/end を置換
                    elem.set("begin", str(int(LOWER)))
                    elem.set("end", str(int(UPPER)))
                    out.write(_tostring(elem))

                else:
                    # depart の有無で分岐
                    if "depart" in elem.attrib:
                        if not past_upper:
                            val = _to_number(elem.attrib.get("depart"))
                            if val is None:
                                # 数値不明 → 単調性が前提なら稀。安全側で出力
                                out.write(_tostring(elem))
                            else:
                                if not started_in_range:
                                    if val < LOWER:
                                        # まだ範囲前：書かずに捨てる
                                        pass
                                    else:
                                        # ここから範囲内に突入
                                        started_in_range = True
                                        if val <= UPPER:
                                            out.write(_tostring(elem))
                                        else:
                                            # 初手でいきなり上限超え
                                            past_upper = True
                                else:
                                    # すでに範囲開始済み
                                    if val <= UPPER:
                                        out.write(_tostring(elem))
                                    else:
                                        past_upper = True
                        # past_upper の場合は depart 付き要素は書かない
                    else:
                        # depart が無い（vType 等）は常に書く
                        out.write(_tostring(elem))

                # メモリ解放：直下要素は処理後に root から除去
                if root is not None:
                    try:
                        root.remove(elem)
                    except Exception:
                        pass

            # 深さを戻す
            depth -= 1

        # ルート閉じタグ
        if root is not None:
            _write_close_root(out, root.tag)

if __name__ == "__main__":
    filter_routes_streaming()
    print(f"完了: {output_file}")
