# -*- coding: utf-8 -*-
"""只读探查：打印真实样本里一个"多条件组合槽位"的原始 XML，用来确认 sv 结构。"""
import sys
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"


def dump(path, want_groups=None, limit=3):
    root = ET.parse(path).getroot()
    slots = root.findall("./member[@name='slots']/list/obj")
    print("=== %s  (slots=%d)" % (path.split("\\")[-1], len(slots)))
    shown = 0
    for i, s in enumerate(slots, 1):
        svs = s.findall("./member[@name='sv']/list/obj")
        groups = [v.find("./int[@name='group']").get("value") for v in svs]
        if want_groups is not None and len(groups) < want_groups:
            continue
        nm = s.find("./member[@name='name']/string[@name='s']")
        act = s.find("./obj[@name='action']")
        key = act.find("./int[@name='key']")
        key2 = act.find("./int[@name='key2']")
        msgs = act.findall("./member[@name='midiMessages']/list/obj")
        print("--- slot #%d name=%r groups=%s key=%s key2=%s msgs=%d" % (
            i, nm.get("value") if nm is not None else None, groups,
            key.get("value") if key is not None else None,
            key2.get("value") if key2 is not None else None, len(msgs)))
        for m in msgs:
            print("      status=%s data1=%s data2=%s" % (
                m.find("./int[@name='status']").get("value"),
                m.find("./int[@name='data1']").get("value"),
                m.find("./int[@name='data2']").get("value")))
        for v in svs:
            d = v.find("./string[@name='description']")
            t = v.find("./string[@name='text']")
            print("      sv group=%s desc=%r text=%r" % (
                v.find("./int[@name='group']").get("value"),
                d.get("value") if d is not None else None,
                t.get("value") if t is not None else None))
        shown += 1
        if shown >= limit:
            break
    print()


if __name__ == "__main__":
    import os
    for f in sys.argv[1:]:
        p = f if os.path.isabs(f) else os.path.join(SRC, f)
        dump(p, want_groups=2, limit=3)
