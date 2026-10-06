# -*- coding: utf-8 -*-
"""只读：找出哪些源文件的 visual 池顺序没被"首次出现顺序"规则命中。"""
import glob
import os
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"

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

    if pool != first:
        print("\n%s   pool=%d first=%d" % (os.path.basename(p), len(pool), len(first)))
        print("   pool 前8 : %s" % pool[:8])
        print("   first前8: %s" % first[:8])
        # 差异位置
        for i, (a, b) in enumerate(zip(pool, first)):
            if a != b:
                print("   首个不同 @%d: pool=%s first=%s" % (i, a, b))
                break
