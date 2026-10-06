# -*- coding: utf-8 -*-
"""反向解析 .expressionmap -> Art 列表。用于 CSV 反向导出与回归验证。"""
import xml.etree.ElementTree as ET
from typing import List
from .model import Art, Cond, KS, KS2, CH, KS_CH, CC_MODE, NONE, clamp_group


class MapDoc(tuple):
    """read_map 的返回值：向下兼容 `(name, arts)` 的二元组解包，
    另外多带一个 `visual_pool` —— 原文件 slotvisuals 池的**原始顺序**。

    那个池只是 Cubase 列表里的显示条目顺序，但它不是任何可推算的排序：
    25 份样本里 19 份就是"第一次出现"的顺序，剩下 6 份是作者当年手点的杂乱顺序。
    想做到逐字节一致，就只能原样记下来再原样写回去。
    """

    visual_pool: List[Cond] = []

    def __new__(cls, name, arts, pool=None):
        obj = super().__new__(cls, (name, arts))
        obj.visual_pool = list(pool or [])
        return obj


def _ival(el, name, default=None):
    if el is None:
        return default
    e = el.find("./int[@name='%s']" % name)
    return e.get("value") if e is not None else default


def _fval(el, name, default=1.0):
    if el is None:
        return default
    e = el.find("./float[@name='%s']" % name)
    return float(e.get("value")) if e is not None else default


def _read_pool(root) -> List[Cond]:
    """按文件里的原始顺序读出 slotvisuals 池。"""
    pool = []
    for v in root.findall("./member[@name='slotvisuals']/list/obj"):
        dv = v.find("./string[@name='description']")
        gv = v.find("./int[@name='group']")
        yv = v.find("./int[@name='symbol']")
        tv = v.find("./string[@name='text']")
        dt = v.find("./int[@name='displaytype']")
        at = v.find("./int[@name='articulationtype']")
        pool.append(Cond(
            group=clamp_group(gv.get("value") if gv is not None else 0),
            description=dv.get("value") if dv is not None else "",
            symbol=int(yv.get("value")) if yv is not None else None,
            text=(tv.get("value") if tv is not None else "") or "",
            displaytype=int(dt.get("value")) if dt is not None else None,
            articulationtype=int(at.get("value")) if at is not None else None,
        ))
    return pool


def read_map(path: str) -> MapDoc:
    root = ET.parse(path).getroot()
    pool = _read_pool(root)
    name_el = root.find("./string[@name='name']")
    map_name = name_el.get("value") if name_el is not None else ""

    arts = []
    for i, s in enumerate(root.findall("./member[@name='slots']/list/obj"), start=1):
        nm = s.find("./member[@name='name']/string[@name='s']")
        name = nm.get("value") if nm is not None else "插槽 %d" % i
        act = s.find("./obj[@name='action']")
        remote = s.find("./obj[@name='remote']")

        ch = int(_ival(act, "channel", "-1"))
        key = int(_ival(act, "key", "-1"))
        key2 = _ival(act, "key2")
        cnum = _ival(act, "controller1num")
        cval = _ival(act, "controller1value")
        rdata = int(_ival(remote, "data1", "-1"))

        if cnum is not None:
            switch = CC_MODE
        elif key2 is not None:
            switch = KS2
        elif key >= 0 and ch >= 0:
            switch = KS_CH
        elif key >= 0:
            switch = KS
        elif ch >= 0:
            switch = CH
        else:
            switch = NONE

        sv_objs = s.findall("./member[@name='sv']/list/obj")
        desc_el = None if not sv_objs else sv_objs[0].find("./string[@name='description']")
        desc = desc_el.get("value") if desc_el is not None else None
        has_visual = bool(sv_objs)

        # ---- 多条件（Art.1-4）：一个 slot 的 sv 里可以有多个不同 group 的 visual ----
        conds = []
        for v in sv_objs:
            gv = v.find("./int[@name='group']")
            dv = v.find("./string[@name='description']")
            yv = v.find("./int[@name='symbol']")
            tv = v.find("./string[@name='text']")
            dt = v.find("./int[@name='displaytype']")
            at = v.find("./int[@name='articulationtype']")
            conds.append(Cond(
                group=clamp_group(gv.get("value") if gv is not None else 0),
                description=dv.get("value") if dv is not None else "",
                symbol=int(yv.get("value")) if yv is not None else None,
                text=(tv.get("value") if tv is not None else "") or "",
                displaytype=int(dt.get("value")) if dt is not None else None,
                articulationtype=int(at.get("value")) if at is not None else None,
            ))
        # 输出事件里的 NoteOn 音符，按条件顺序回填（样本中两者顺序一致）
        msg_notes = []
        for m in act.findall("./member[@name='midiMessages']/list/obj"):
            st = m.find("./int[@name='status']")
            d1 = m.find("./int[@name='data1']")
            if st is not None and d1 is not None and int(st.get("value")) == 144:
                msg_notes.append(int(d1.get("value")))
        if conds and len(msg_notes) >= len(conds):
            for c, n in zip(conds, msg_notes):
                c.note = n

        arts.append(Art(
            name=name,
            switch=switch,
            note=key if key >= 0 else None,
            note2=int(key2) if key2 is not None else None,
            channel=ch + 1 if ch >= 0 else None,
            cc_num=int(cnum) if cnum is not None else None,
            cc_val=int(cval) if cval is not None else None,
            color=int(_ival(s, "color", "1")),
            length_fact=_fval(act, "lengthFact"),
            velocity_fact=_fval(act, "velocityFact"),
            min_velocity=int(_ival(act, "minVelocity", "0")) or 0,
            max_velocity=int(_ival(act, "maxVelocity", "127")) if _ival(act, "maxVelocity") else 127,
            min_pitch=int(_ival(act, "minPitch", "0")) or 0,
            max_pitch=int(_ival(act, "maxPitch", "127")) if _ival(act, "maxPitch") else 127,
            transpose=int(_ival(act, "transpose", "0")),
            remote=rdata if rdata >= 0 else None,
            description=desc,
            order=i,
            has_visual=has_visual,
            conditions=conds,
            symbol=(conds[0].symbol if conds and len(conds) == 1 else None),
            text=(conds[0].text if conds and len(conds) == 1 else ""),
            displaytype=(conds[0].displaytype if conds and len(conds) == 1 else None),
            articulationtype=(conds[0].articulationtype if conds and len(conds) == 1 else None),
        ))
    return MapDoc(map_name, arts, pool)
