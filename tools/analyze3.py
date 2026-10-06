# -*- coding: utf-8 -*-
"""第三轮：key2 双键样本 / remote 分布 / ID 唯一性 / slotvisuals 对应 / float 取值。只读。"""
import glob
import os
import sys
import collections
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\Cubase project\模板文件\技法"
files = sorted(glob.glob(os.path.join(SRC, "*.expressionmap")))


def ival(el, name):
    e = el.find("./int[@name='%s']" % name)
    return e.get("value") if e is not None else None


def sval(el, name):
    e = el.find("./string[@name='%s']" % name)
    return e.get("value") if e is not None else None


remote_d1 = collections.Counter()
remote_st = collections.Counter()
float_vals = collections.Counter()
dup_in_file = []
vis_mismatch = []
key2_sample = None
str_names = collections.Counter()

for f in files:
    root = ET.parse(f).getroot()
    ids = [el.get("ID") for el in root.iter() if "ID" in el.attrib]
    if len(ids) != len(set(ids)):
        dup_in_file.append((os.path.basename(f), len(ids), len(set(ids))))

    for el in root.iter():
        if el.tag == "float":
            float_vals[(el.get("name"), el.get("value"))] += 1
        if el.tag == "string":
            str_names[el.get("name")] += 1

    for s in root.findall("./member[@name='slots']/list/obj"):
        r = s.find("./obj[@name='remote']")
        remote_d1[ival(r, "data1")] += 1
        remote_st[ival(r, "status")] += 1
        act = s.find("./obj[@name='action']")
        if ival(act, "key2") is not None and key2_sample is None:
            key2_sample = (os.path.basename(f), s)

    svs = root.findall("./member[@name='slotvisuals']/list/obj")
    sl = root.findall("./member[@name='slots']/list/obj")
    a = [(ival(v, "symbol"), sval(v, "description"), ival(v, "displaytype")) for v in svs]
    b = []
    for s in sl:
        for v in s.findall("./member[@name='sv']/list/obj"):
            b.append((ival(v, "symbol"), sval(v, "description"), ival(v, "displaytype")))
    if len(a) != len(b):
        vis_mismatch.append((os.path.basename(f), len(a), len(b), "数量不等"))
    elif a != b:
        same = sum(1 for x, y in zip(a, b) if x == y)
        vis_mismatch.append((os.path.basename(f), len(a), len(b), "顺序/内容差异 %d 处" % (len(a) - same)))

print("--- remote(PSlotThruTrigger) status 分布 ---")
print(dict(remote_st.most_common()))
print("--- remote data1 分布 ---")
print(dict(remote_d1.most_common(10)))
print("\n--- float 字段取值 (非1的) ---")
print({k: v for k, v in float_vals.items() if v})
print("\n--- string 字段名 ---")
print(dict(str_names.most_common()))
print("\n--- 同文件内 ID 重复的文件 ---")
print(dup_in_file if dup_in_file else "无（每个文件内 ID 全唯一）")
print("\n--- slotvisuals 与 slots/sv 对应关系 ---")
print(vis_mismatch if vis_mismatch else "全部 25 个文件：数量与顺序完全一致")

print("\n" + "=" * 70)
print("### key2 双键样本")
if key2_sample:
    print("来自:", key2_sample[0])
    print(ET.tostring(key2_sample[1], encoding="unicode"))
