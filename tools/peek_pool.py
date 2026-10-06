# -*- coding: utf-8 -*-
"""只读探查：slotvisuals 池的内容与顺序，以及单条件槽位长什么样。"""
import sys
import os
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"


def dump(path):
    root = ET.parse(path).getroot()
    pool = root.findall("./member[@name='slotvisuals']/list/obj")
    print("=== %s" % path.split("\\")[-1])
    print("pool size = %d" % len(pool))
    for v in pool:
        d = v.find("./string[@name='description']")
        g = v.find("./int[@name='group']")
        print("   pool: group=%s desc=%r" % (g.get("value") if g is not None else None,
                                             d.get("value") if d is not None else None))
    slots = root.findall("./member[@name='slots']/list/obj")
    print("slots = %d" % len(slots))
    for i, s in enumerate(slots, 1):
        svs = s.findall("./member[@name='sv']/list/obj")
        groups = [v.find("./int[@name='group']").get("value") for v in svs]
        nm = s.find("./member[@name='name']/string[@name='s']")
        act = s.find("./obj[@name='action']")
        key = act.find("./int[@name='key']")
        ch = act.find("./int[@name='channel']")
        rem = s.find("./obj[@name='remote']")
        rd = rem.find("./int[@name='data1']") if rem is not None else None
        print("  #%-3d name=%-14r groups=%-10s key=%-4s ch=%-3s remote=%-4s msgs=%d" % (
            i, nm.get("value") if nm is not None else None, ",".join(groups),
            key.get("value") if key is not None else None,
            ch.get("value") if ch is not None else None,
            rd.get("value") if rd is not None else None,
            len(act.findall("./member[@name='midiMessages']/list/obj"))))
    print()


if __name__ == "__main__":
    for f in sys.argv[1:]:
        p = f if os.path.isabs(f) else os.path.join(SRC, f)
        dump(p)
