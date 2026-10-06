# -*- coding: utf-8 -*-
"""只读探针：测哪种判定规则能把"原文件里 visual 的 symbol 值"从数据本身推出来。

做法：对 25 个文件、每个 visual 记录 (表达式定义, 它在池里的下标, 它的 symbol)，
再按各种假设去猜 symbol，统计命中率。
"""
import glob
import os
import xml.etree.ElementTree as ET

SRC = r"E:\Cubase project\模板文件\技法"


def collect(p):
    r = ET.parse(p).getroot()
    pool = []
    for v in r.findall("./member[@name='slotvisuals']/list/obj"):
        pool.append({
            "group": v.find("./int[@name='group']").get("value"),
            "desc": v.find("./string[@name='description']").get("value"),
            "symbol": v.find("./int[@name='symbol']").get("value"),
        })
    slots = []
    for i, s in enumerate(r.findall("./member[@name='slots']/list/obj"), 1):
        nm = s.find("./member[@name='name']/string[@name='s']")
        svs = s.findall("./member[@name='sv']/list/obj")
        slots.append({
            "i": i,
            "name": nm.get("value") if nm is not None else "",
            "sv": [{"group": v.find("./int[@name='group']").get("value"),
                    "desc": v.find("./string[@name='description']").get("value"),
                    "id": v.get("ID")} for v in svs],
        })
    return pool, slots


rows = []
for p in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    pool, slots = collect(p)
    order = {(x["group"], x["desc"]): i for i, x in enumerate(pool)}
    # 每个 visual 在池里的下标 与 它的 symbol
    for x in pool:
        rows.append({"file": os.path.basename(p), "idx": order[(x["group"], x["desc"])],
                     "group": x["group"], "desc": x["desc"], "symbol": x["symbol"],
                     "pool_size": len(pool)})

print("共 %d 个 visual" % len(rows))

# 假设 A：每文件内部按池顺序，symbol 取自该文件自定义的一组值（无规律）→ 无法推导
# 假设 B：symbol 与 (group, desc) 全局对应（同名同层用不同 symbol？）
from collections import defaultdict, Counter
m = defaultdict(set)
for r in rows:
    m[(r["group"], r["desc"])].add(r["symbol"])
multi = {k: v for k, v in m.items() if len(v) > 1}
print("同名同层却有多套 symbol 的：%d / %d" % (len(multi), len(m)))
for k, v in list(multi.items())[:8]:
    print("   ", k, sorted(v))

# 假设 C：symbol 是某个固定集合里的值，按池下标轮取
cnt = Counter(r["symbol"] for r in rows)
print("symbol 取值分布 top:", cnt.most_common(20))

# 假设 D：每个文件里，池下标的顺序 << 某个步长 得到 symbol？
for f in sorted({r["file"] for r in rows})[:5]:
    sub = sorted([r for r in rows if r["file"] == f], key=lambda x: x["idx"])
    print("\n%s" % f)
    for r in sub:
        print("   idx=%-3d grp=%s sym=%-5s %s" % (r["idx"], r["group"], r["symbol"], r["desc"]))
