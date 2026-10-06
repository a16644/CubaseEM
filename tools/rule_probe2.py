# -*- coding: utf-8 -*-
"""只读：检验"从 Cubase 导出的表情映射里，音源作者本来就不带乐谱符号"这个结论。

判据：25 个文件本来就不是均匀分布 —— 如果作者在 Cubase 里配了符号，
同一个技法名（同层）在不同音源里应当拿到同一个符号；实测是多套值，说明符号
是导入其它 DAW 映射时顺带带过来的，属于不可推导的输入。
"""
import glob
import os
import xml.etree.ElementTree as ET
from collections import defaultdict

SRC = r"E:\Cubase project\模板文件\技法"

rows = []
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    r = ET.parse(p).getroot()
    fname = os.path.basename(p)
    for v in r.findall("./member[@name='slotvisuals']/list/obj"):
        rows.append({
            "file": fname,
            "group": v.find("./int[@name='group']").get("value"),
            "desc": (v.find("./string[@name='description']").get("value") or "").strip().lower(),
            "symbol": v.find("./int[@name='symbol']").get("value"),
        })

by_name = defaultdict(lambda: defaultdict(list))
for x in rows:
    by_name[(x["group"], x["desc"])][x["symbol"]].append(x["file"])

print("同名同层、跨越多个文件却符号不一致的技法：")
n = 0
for k, v in sorted(by_name.items()):
    files = {f for fs in v.values() for f in fs}
    if len(v) > 1 and len(files) > 1:
        n += 1
        if n <= 12:
            print("   %-18s %s" % (str(k), {s: len(f) for s, f in v.items()}))
print("合计 %d 组（说明符号不是按技法名统一规定的）" % n)

# 每个文件的符号集合，看有没有"整文件统一"的
print("\n每个文件的符号取值集合：")
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    r = ET.parse(p).getroot()
    syms = [v.find("./int[@name='symbol']").get("value")
            for v in r.findall("./member[@name='slotvisuals']/list/obj")]
    uniq = sorted(set(syms))
    print("   %-52s %d 种 %s" % (os.path.basename(p), len(uniq), uniq[:8]))
