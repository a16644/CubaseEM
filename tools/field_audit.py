# -*- coding: utf-8 -*-
"""只读：审计 USlotVisuals 里还有一个 displaytype 字段各文件怎么用的。"""
import glob
import os
import xml.etree.ElementTree as ET
from collections import Counter

SRC = r"E:\Cubase project\模板文件\技法"

c = Counter()
per_file = {}
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    r = ET.parse(p).getroot()
    vals = Counter()
    for v in r.findall("./member[@name='slotvisuals']/list/obj"):
        dt = v.find("./int[@name='displaytype']")
        t = v.find("./string[@name='text']")
        vals[dt.get("value") if dt is not None else None] += 1
        c[(dt.get("value") if dt is not None else None,
           bool(t.get("value")) if t is not None else None)] += 1
    per_file[os.path.basename(p)] = dict(vals)

print("(displaytype, text 非空) 分布:", dict(c))
print()
for k, v in per_file.items():
    if "1" in v:
        print("  %-52s %s" % (k, v))
