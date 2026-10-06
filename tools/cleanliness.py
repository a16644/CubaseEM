# -*- coding: utf-8 -*-
"""只读：统计源文件里"孤儿 visual"（在池里但没有任何 slot 用它）有多少。"""
import glob
import os
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"

tot_pool = tot_used = tot_orphan = 0
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    r = ET.parse(p).getroot()
    pool = {(v.find("./int[@name='group']").get("value"),
             v.find("./string[@name='description']").get("value"))
            for v in r.findall("./member[@name='slotvisuals']/list/obj")}
    used = set()
    for s in r.findall("./member[@name='slots']/list/obj"):
        nm = s.find("./member[@name='name']/string[@name='s']")
        nmv = nm.get("value") if nm is not None else ""
        for v in s.findall("./member[@name='sv']/list/obj"):
            used.add((v.find("./int[@name='group']").get("value"),
                      v.find("./string[@name='description']").get("value") or nmv))
    orphan = pool - used
    tot_pool += len(pool)
    tot_used += len(used)
    tot_orphan += len(orphan)
    if orphan:
        print("  %-52s 池 %d，孤儿 %d：%s" % (os.path.basename(p), len(pool),
                                             len(orphan), sorted(orphan)[:4]))

print("\n池总数 %d，被引用 %d，孤儿 %d" % (tot_pool, tot_used, tot_orphan))
