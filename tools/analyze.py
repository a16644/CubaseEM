# -*- coding: utf-8 -*-
"""
只读分析 Cubase .expressionmap 样本 —— 绝不写入源文件。
用法: python tools/analyze.py
"""
import glob
import os
import sys
import collections
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"E:\Cubase project\模板文件\技法"
files = sorted(glob.glob(os.path.join(SRC, "*.expressionmap")))

tag_counter = collections.Counter()
class_counter = collections.Counter()
int_names = collections.Counter()
color_vals = collections.Counter()
status_vals = collections.Counter()
ids = collections.Counter()
per_file = []
controller_kinds = collections.Counter()
slot_child_order = collections.Counter()
action_child_order = collections.Counter()

for f in files:
    root = ET.parse(f).getroot()
    tag_counter[root.tag] += 1
    for el in root.iter():
        tag_counter[el.tag] += 1
        if "class" in el.attrib:
            class_counter[el.attrib["class"]] += 1
        if "ID" in el.attrib:
            ids[el.attrib["ID"]] += 1
        if el.tag == "int":
            n = el.attrib.get("name")
            int_names[n] += 1
            if n == "color":
                color_vals[el.attrib.get("value")] += 1
            if n == "status":
                status_vals[el.attrib.get("value")] += 1

    slots = root.findall("./member[@name='slots']/list/obj")
    for s in slots:
        slot_child_order[tuple(
            (c.tag, c.attrib.get("class") or c.attrib.get("name")) for c in s
        )] += 1
        act = s.find("./obj[@name='action']")
        if act is not None:
            action_child_order[tuple(
                (c.tag, c.attrib.get("class") or c.attrib.get("name")) for c in act
            )] += 1

    ctrl = root.find("./member[@name='controller']")
    if ctrl is None:
        controller_kinds["<missing>"] += 1
    elif len(ctrl) == 0:
        controller_kinds["<empty>"] += 1
    else:
        controller_kinds[tuple(c.tag + ":" + (c.attrib.get("name") or "?") for c in ctrl)] += 1

    sv = root.find("./member[@name='slotvisuals']")
    per_file.append((os.path.basename(f), len(slots),
                     len(sv.findall("./list/obj")) if sv is not None else -1,
                     len(ctrl) if ctrl is not None else -1))

print("=" * 70)
print("文件数:", len(files))
print("=" * 70)
print("\n--- 根标签 ---")
print(dict(tag_counter.most_common(6)))

print("\n--- 所有 class ---")
for k, v in class_counter.most_common():
    print(f"{v:6d}  {k}")

print("\n--- int 字段名 TOP30 ---")
for k, v in int_names.most_common(30):
    print(f"{v:6d}  {k}")

print("\n--- status 取值分布 (144=NoteOn 176=CC 192=PC) ---")
for k, v in status_vals.most_common():
    print(f"{v:6d}  status={k}")

print("\n--- color 取值分布 (TOP20) ---")
for k, v in color_vals.most_common(20):
    print(f"{v:6d}  color={k}")

print("\n--- PSoundSlot 子元素顺序 ---")
for k, v in slot_child_order.most_common():
    print(f"{v:6d}  {k}")

print("\n--- PSlotMidiAction 子元素顺序 ---")
for k, v in action_child_order.most_common():
    print(f"{v:6d}  {k}")

print("\n--- controller 结构 ---")
for k, v in controller_kinds.most_common():
    print(f"{v:6d}  {k}")

print("\n--- 每文件: slot数 / slotvisuals数 / controller子数 ---")
for name, nslot, nsv, nctrl in per_file:
    print(f"{nslot:4d} slots | {nsv:4d} visuals | {nctrl:3d} ctrl | {name}")

print("\n--- ID 统计 ---")
print("唯一 ID 数:", len(ids), " 总出现:", sum(ids.values()))
dup = [(k, v) for k, v in ids.items() if v > 1]
print("重复 ID 数:", len(dup))
