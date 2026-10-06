# -*- coding: utf-8 -*-
"""只读：判断 slotvisuals 池的顺序是按什么排的。
候选：① 按 (group, description) 字典序 ② 按首次出现顺序。
"""
import glob
import os
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"

ok_key = ok_first = 0
total = 0
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    r = ET.parse(p).getroot()
    pool = [(v.find("./int[@name='group']").get("value"),
             v.find("./string[@name='description']").get("value"))
            for v in r.findall("./member[@name='slotvisuals']/list/obj")]

    first, seen = [], set()
    for s in r.findall("./member[@name='slots']/list/obj"):
        nm = s.find("./member[@name='name']/string[@name='s']")
        nmv = nm.get("value") if nm is not None else ""
        for v in s.findall("./member[@name='sv']/list/obj"):
            g = v.find("./int[@name='group']").get("value")
            d = v.find("./string[@name='description']").get("value")
            k = (g, d or nmv)
            if k not in seen:
                seen.add(k)
                first.append(k)

    total += 1
    if pool == sorted(pool):
        ok_key += 1
    if pool == first:
        ok_first += 1
    if pool != sorted(pool) and pool != first:
        print("!! %-50s pool=%d sorted=%s first=%s" % (
            os.path.basename(p), len(pool), pool == sorted(pool), pool == first))

print("文件 %d：按 (group,desc) 字典序命中 %d，按首次出现顺序命中 %d"
      % (total, ok_key, ok_first))
