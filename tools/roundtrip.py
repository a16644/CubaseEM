# -*- coding: utf-8 -*-
"""
全量往返回归验证（只读源文件，产物写在 out/_rt/）：
  真实样本 -> read_map -> renderer 重新生成 -> read_map -> 逐字段比对
任何字段对不上都说明渲染器丢信息。
"""
import glob
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from em.reader import read_map          # noqa: E402
from em.renderer import render_map      # noqa: E402
from em.registry import get_brand       # noqa: E402

SRC = r"E:\Cubase project\模板文件\技法"
TMP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "out", "_rt"))
os.makedirs(TMP, exist_ok=True)

FIELDS = ("name", "switch", "note", "note2", "channel", "cc_num", "cc_val",
          "color", "length_fact", "velocity_fact", "transpose", "remote",
          "description", "min_velocity", "max_velocity",
          "min_pitch", "max_pitch")


def cond_sig(a):
    """多条件签名：(group, description, note, symbol) 序列。"""
    return tuple((int(c.group), c.description, c.note, c.symbol, c.text,
                  c.articulationtype) for c in a.conditions)

brand = get_brand("kontakt")
ok_files, bad_files = 0, []
total_slots, diff_slots = 0, 0

for f in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    base = os.path.basename(f)
    try:
        name, arts = read_map(f)
    except Exception as ex:
        bad_files.append((base, "解析失败: %s" % ex))
        continue

    # 结构合法性 + 元素集合
    slots = brand.build_all(arts, brand.defaults)
    xml_text = render_map(name, slots)
    tmp = os.path.join(TMP, base)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(xml_text)
    try:
        ET.parse(tmp)
        name2, arts2 = read_map(tmp)
    except Exception as ex:
        bad_files.append((base, "生成文件无法回读: %s" % ex))
        continue

    diffs = []
    if name2 != name:
        diffs.append("映射名: %r != %r" % (name, name2))
    if len(arts2) != len(arts):
        diffs.append("技法数: %d != %d" % (len(arts), len(arts2)))
    for i, (a, b) in enumerate(zip(arts, arts2), start=1):
        total_slots += 1
        for fld in FIELDS:
            va, vb = getattr(a, fld), getattr(b, fld)
            if va != vb:
                diff_slots += 1
                diffs.append("#%d %s: %s=%r != %r" % (i, a.name, fld, va, vb))
                break
        if cond_sig(a) != cond_sig(b):
            diff_slots += 1
            diffs.append("#%d %s: conditions=%r != %r" % (i, a.name, cond_sig(a), cond_sig(b)))

    # 元素 class 集合一致性
    def cls(p):
        return {e.get("class") for e in ET.parse(p).getroot().iter() if e.get("class")}
    if cls(f) != cls(tmp):
        diffs.append("元素类型集合不同: %s" % (cls(f) ^ cls(tmp)))

    if diffs:
        bad_files.append((base, diffs[:4]))
    else:
        ok_files += 1

print("=" * 68)
print("往返回归：源文件 %d 个" % (ok_files + len(bad_files)))
print("完全一致: %d   有差异: %d" % (ok_files, len(bad_files)))
print("参与比对的 slot 总数: %d，其中字段不符: %d" % (total_slots, diff_slots))
print("=" * 68)
for base, d in bad_files:
    print("\n[差异] %s" % base)
    if isinstance(d, list):
        for x in d:
            print("   " + str(x))
    else:
        print("   " + str(d))
