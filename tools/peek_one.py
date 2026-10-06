# -*- coding: utf-8 -*-
"""只读：看单个槽位的完整 XML 结构，确认组合槽的 key/key2/remote 怎么存。"""
import os
import sys
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"


def raw(path, idx):
    txt = open(path, "r", encoding="utf-8-sig").read()
    root = ET.fromstring(txt)
    slots = root.findall("./member[@name='slots']/list/obj")
    s = slots[idx - 1]
    # 用 ElementTree 反序列化回来打印
    body = ET.tostring(s, encoding="unicode")
    import re
    body = re.sub(r"><", ">\n<", body)
    print(body)


if __name__ == "__main__":
    f = sys.argv[1]
    p = f if os.path.isabs(f) else os.path.join(SRC, f)
    raw(p, int(sys.argv[2]) if len(sys.argv) > 2 else 19)
