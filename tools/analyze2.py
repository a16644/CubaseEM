# -*- coding: utf-8 -*-
"""第二轮：只看关键字段取值 + 抽典型 slot 原文。只读。"""
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


act_ch = collections.Counter()
nc_ch = collections.Counter()
key_vals = collections.Counter()
key2_vals = collections.Counter()
ev = collections.Counter()
vis = collections.Counter()
zero_msg_ch = collections.Counter()
ccnum = collections.Counter()
ccval = collections.Counter()
samples = {}
n_msg = collections.Counter()
slot_table = []

for f in files:
    root = ET.parse(f).getroot()
    for s in root.findall("./member[@name='slots']/list/obj"):
        act = s.find("./obj[@name='action']")
        nc = act.find("./member[@name='noteChanger']/list/obj")
        a_ch = ival(act, "channel")
        n_ch = ival(nc, "channel")
        k, k2 = ival(act, "key"), ival(act, "key2")
        c1, c1v = ival(act, "controller1num"), ival(act, "controller1value")
        act_ch[a_ch] += 1
        nc_ch[n_ch] += 1
        key_vals[k] += 1
        if k2 is not None:
            key2_vals[k2] += 1
        if c1 is not None:
            ccnum[c1] += 1
            ccval[c1v] += 1
        msgs = act.findall("./member[@name='midiMessages']/list/obj")
        n_msg[len(msgs)] += 1
        if len(msgs) == 0:
            zero_msg_ch[(a_ch, n_ch)] += 1
        for m in msgs:
            ev[(ival(m, "status"), ival(m, "data2"))] += 1
        for v in s.findall("./member[@name='sv']/list/obj"):
            vis[(ival(v, "displaytype"), ival(v, "articulationtype"),
                 ival(v, "symbol"), ival(v, "group"))] += 1

        nm = sval(s.find("./member[@name='name']"), "s")
        slot_table.append((os.path.basename(f), nm, a_ch, n_ch, k, k2, c1, c1v, len(msgs)))

        if "cc" not in samples and c1 is not None:
            samples["cc"] = (os.path.basename(f), s)
        if "two_msg" not in samples and len(msgs) == 2 and k2 is None:
            samples["two_msg"] = (os.path.basename(f), s)
        if "zero_msg" not in samples and len(msgs) == 0:
            samples["zero_msg"] = (os.path.basename(f), s)
        if "ch_set" not in samples and a_ch not in ("-1", None):
            samples["ch_set"] = (os.path.basename(f), s)

print("--- action/channel 取值 ---")
print(dict(act_ch.most_common(20)))
print("\n--- noteChanger/channel 取值 ---")
print(dict(nc_ch.most_common(20)))
print("\n--- key 取值分布 ---")
print(sorted((int(k), v) for k, v in key_vals.items() if k is not None))
print("\n--- key2 取值分布 ---")
print(sorted((int(k), v) for k, v in key2_vals.items() if k is not None))
print("\n--- midiMessages 条数 ---")
print(dict(n_msg.most_common()))
print("\n--- 0 条消息的 slot: (action.ch, noteChanger.ch) ---")
print(dict(zero_msg_ch.most_common()))
print("\n--- controller1num / value ---")
print(dict(ccnum.most_common()), dict(ccval.most_common()))
print("\n--- POutputEvent (status,data2) ---")
print(dict(ev.most_common(20)))
print("\n--- USlotVisuals (displaytype,articulationtype,symbol,group) TOP12 ---")
for k, v in vis.most_common(12):
    print(f"{v:5d}  {k}")

print("\n--- 全部 slot 一览 (文件|名称|act.ch|nc.ch|key|key2|cc|ccv|msg数) ---")
for r in slot_table:
    print(" | ".join(str(x) for x in r))

for tag in ("cc", "two_msg", "zero_msg", "ch_set"):
    print("\n" + "=" * 70)
    print("### 典型样本:", tag)
    if tag not in samples:
        print("(未找到)")
        continue
    name, s = samples[tag]
    print("来自:", name)
    print(ET.tostring(s, encoding="unicode"))
