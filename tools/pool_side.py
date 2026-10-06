# -*- coding: utf-8 -*-
"""只读：把某个文件"池"和"新生成"的 visual 列表并排打出来，定位顺序差异的成因。"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from em.reader import read_map            # noqa: E402

SRC = r"E:\Cubase project\模板文件\技法"


def sig(v):
    return "%s|%s|sym=%s|dt=%s|txt=%s" % (
        v.find("./int[@name='group']").get("value"),
        v.find("./string[@name='description']").get("value"),
        v.find("./int[@name='symbol']").get("value"),
        v.find("./int[@name='displaytype']").get("value"),
        v.find("./string[@name='text']").get("value"))


def main(fn):
    p = os.path.join(SRC, fn)
    r = ET.parse(p).getroot()
    pool = [sig(v) for v in r.findall("./member[@name='slotvisuals']/list/obj")]

    _n, arts = read_map(p)
    new, seen = [], set()
    for a in arts:
        if not a.has_visual:
            continue
        for c in a.conditions:
            k = (c.description, int(c.group))
            if k in seen:
                continue
            seen.add(k)
            new.append("%s|%s|sym=%s|dt=%s|txt=%s" % (
                c.group, c.description, c.symbol,
                1 if c.text else (c.displaytype or 0), c.text))
    new.sort()

    print("池 %d 条 / 新生成 %d 条" % (len(pool), len(new)))
    print("\n%-5s %-42s | %s" % ("idx", "原池", "新生成"))
    for i in range(max(len(pool), len(new))):
        a = pool[i] if i < len(pool) else ""
        b = new[i] if i < len(new) else ""
        mark = "  " if a == b else "≠ "
        print("%s%-4d %-42s | %s" % (mark, i, a, b))


if __name__ == "__main__":
    main(sys.argv[1])
