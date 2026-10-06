# -*- coding: utf-8 -*-
"""只读：验证 slotvisuals 池的去重规则 —— 按 description 去重 还是按 (group, description) 去重。"""
import os
import glob
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"


def actual_pool(path):
    r = ET.parse(path).getroot()
    return [(v.find("./int[@name='group']").get("value"),
             v.find("./string[@name='description']").get("value"))
            for v in r.findall("./member[@name='slotvisuals']/list/obj")]


def from_slots(path):
    """按 slot 顺序遍历，两种去重规则各算一次。"""
    r = ET.parse(path).getroot()
    by_desc, by_pair = [], []
    sd, sp = set(), set()
    for s in r.findall("./member[@name='slots']/list/obj"):
        svs = s.findall("./member[@name='sv']/list/obj")
        if not svs:
            continue
        nm = s.find("./member[@name='name']/string[@name='s']")
        nmv = nm.get("value") if nm is not None else ""
        for v in svs:
            g = v.find("./int[@name='group']").get("value")
            d = v.find("./string[@name='description']").get("value")
            key = d or nmv
            if key not in sd:
                sd.add(key)
                by_desc.append((g, key))
            if (g, key) not in sp:
                sp.add((g, key))
                by_pair.append((g, key))
    return by_desc, by_pair


def main():
    ok_desc = ok_pair = 0
    total = 0
    for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
        a = actual_pool(p)
        d1, d2 = from_slots(p)
        total += 1
        m1 = len(a) == len(d1) and all(x[1] == y[1] for x, y in zip(a, d1))
        m2 = len(a) == len(d2) and all(x[1] == y[1] for x, y in zip(a, d2))
        ok_desc += 1 if m1 else 0
        ok_pair += 1 if m2 else 0
        if not (m1 or m2):
            print("!! %-52s actual=%d desc=%d pair=%d" % (
                os.path.basename(p), len(a), len(d1), len(d2)))
        elif not m1 or not m2:
            print("   %-52s actual=%d desc_rule=%s pair_rule=%s" % (
                os.path.basename(p), len(a), "OK" if m1 else "X", "OK" if m2 else "X"))
    print("\n文件数 %d：按 description 去重命中 %d，按 (group,description) 去重命中 %d"
          % (total, ok_desc, ok_pair))


if __name__ == "__main__":
    main()
