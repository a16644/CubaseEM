# -*- coding: utf-8 -*-
"""
验证「符号可以是文本」与「显示方式」这两条规则（只读，产物写在 out/_symtest/）。

Cubase 发音法面板最左边那列（Art.）是给**使用者**看的；左边的名称列是给
**做表情的人**看的。所以显示这块有两种模式：
  symbol 模式  displaytype=0 + <int name="symbol">  -> 宿主里画一个小记号（≡ · −）
  text   模式  displaytype=1 + <string name="text"> -> 宿主里直接写字

规则：
  1. 「符号」格填数字    -> 符号模式（跟改动前一模一样，不能动）
  2. 「符号」格填文字    -> 文本模式，这段文字进 text
  3. 二者都空 + 显示方式=文本 -> 文本模式，文字取技法名
  4. 二者都空 + 显示方式=符号 / 自动 -> 符号模式（原样，回归要过）
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from em.parsers import parse_csv                      # noqa: E402
from em.registry import get_brand                     # noqa: E402
from em.renderer import render_map                    # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TMP = os.path.join(ROOT, "out", "_symtest")
os.makedirs(TMP, exist_ok=True)
CSV = os.path.join(TMP, "in.csv")

HEADER = ("map_name,name,switch,note,symbol,text,display,"
          "articulationtype,min_velocity,max_velocity")

ROWS = [
    # name,   note, symbol, text,  display
    ("滑音",  24, "滑音", "",   ""),      # 符号格填文字 -> 文本模式
    ("断奏",  25, "73",   "",   ""),      # 符号格填编号 -> 符号模式（不变）
    ("长音",  26, "",     "",   ""),      # 什么都没填   -> 符号模式（不变）
]

brand = get_brand("kontakt")
fails = []


def visual_of(xml_text: str):
    """-> {description: (displaytype, symbol, text)}，直接按名字定位，顺序无关。"""
    root = ET.fromstring(xml_text.encode("utf-8"))
    out = {}
    for v in root.findall("./member[@name='slotvisuals']/list/obj"):
        desc = v.find("./string[@name='description']")
        name = desc.get("value") if desc is not None else ""
        if name in out:
            continue
        iv = lambda n: (v.find("./int[@name='%s']" % n).get("value")
                        if v.find("./int[@name='%s']" % n) is not None else "")
        t = v.find("./string[@name='text']")
        out[name] = (iv("displaytype"), iv("symbol"),
                     t.get("value") if t is not None else "")
    return out


def build(rows, mode=None):
    path = os.path.join(TMP, "cur.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\ufeff" + HEADER + "\n")
        for name, note, sym, txt, disp in rows:
            f.write("%s,%s,ks,%d,%s,%s,%s,1,0,127\n"
                    % ("测试", name, note, sym, txt, disp or mode or ""))
    arts = parse_csv(path)
    if mode:
        from em.model import normalize_display_mode
        m = normalize_display_mode(mode)
        for a in arts:
            a.display_mode = m
            for c in a.conditions:
                if c.display_mode is None:
                    c.display_mode = m
    xml_text = render_map("测试", brand.build_all(arts, brand.defaults))
    p = os.path.join(TMP, "cur.expressionmap")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(xml_text)
    ET.parse(p)                      # 必须能过 XML 校验
    return visual_of(xml_text)


def check(label, got, want):
    if got == want:
        print("  ✔ %s" % label)
    else:
        print("  ✗ %s\n      期望 %s\n      实际 %s" % (label, want, got))
        fails.append(label)


print("符号 / 显示方式验证")

# 默认（auto）：只有「符号」格填了文字的那一行变文本，其它两行原样不动
v = build(ROWS, None)
check("符号格填文字 -> 文本模式，那段字进 text",
      v.get("滑音"), ("1", "0", "滑音"))
check("符号格填编号 -> 符号模式，编号保住",
      v.get("断奏"), ("0", "73", ""))
check("都空 -> 符号模式（回归底线，不能变）",
      v.get("长音"), ("0", "0", ""))

# 显示方式 = 文本：三行全变文本，没短标签的用技法名顶上
v = build(ROWS, "text")
check("显示方式=文本 -> 三行都是文本模式",
      v.get("滑音"), ("1", "0", "滑音"))
check("显示方式=文本 -> 没有短标签的用技法名顶上",
      v.get("断奏"), ("1", "73", "断奏"))
check("显示方式=文本 -> 行内符号编号照留（文本模式用不上，但不丢）",
      v.get("长音"), ("1", "0", "长音"))

# 显示方式 = 符号：非文字型保持原样
v = build(ROWS, "symbol")
check("显示方式=符号 -> 填文字的那行仍按文字显示（不吞用户填的内容）",
      v.get("滑音"), ("1", "0", "滑音"))
check("显示方式=符号 -> 其它行符号模式不变",
      v.get("断奏"), ("0", "73", ""))

# 短标签优先：显式 text 列不被技法名覆盖
v = build([("长音", 26, "", "短标", "text")], None)
check("显式短标签优先于技法名", v.get("长音"), ("1", "0", "短标"))

# CSV 里直接写 display 列（别人手工改表也能用）
v = build([("长音", 26, "", "", "text")], None)
check("CSV display 列 -> 文本模式", v.get("长音"), ("1", "0", "长音"))
v = build([("长音", 26, "", "", "symbol")], None)
check("CSV display 列 = 符号 -> 符号模式", v.get("长音"), ("0", "0", ""))

print("\n%s（%d 项失败）" % ("全部通过" if not fails else "有失败", len(fails)))
sys.exit(1 if fails else 0)
