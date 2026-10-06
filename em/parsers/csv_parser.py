# -*- coding: utf-8 -*-
"""CSV / Excel 输入解析。列名宽容匹配（中英文均可），缺列自动跳过。"""
import csv
import os
from typing import List
from ..model import (Art, decode_conditions, normalize_symbol,
                     normalize_display_mode)
from .common import parse_note, norm_switch, to_int, to_float, to_bool

# 列名别名 -> 字段
ALIASES = {
    "name": ("name", "slot_name", "\u540d\u79f0", "\u6280\u6cd5", "\u63d2\u69fd", "articulation"),
    "switch": ("switch", "type", "\u65b9\u5f0f", "\u5207\u6362", "\u7c7b\u578b", "mode"),
    "note": ("note", "key", "keyswitch", "\u97f3\u7b26", "\u952e", "\u97f3"),
    "note2": ("note2", "key2", "\u97f3\u7b262", "\u7b2c\u4e8c\u97f3\u7b26"),
    "channel": ("channel", "ch", "\u901a\u9053"),
    "cc_num": ("cc_num", "cc", "ccno", "cc\u53f7"),
    "cc_val": ("cc_val", "ccval", "cc\u503c", "value"),
    "color": ("color", "\u989c\u8272"),
    "length_fact": ("length", "length_fact", "\u957f\u5ea6"),
    "velocity_fact": ("velocity", "velocity_fact", "\u529b\u5ea6"),
    "transpose": ("transpose", "\u79fb\u8c03"),
    "remote": ("remote", "\u8fdc\u7a0b"),
    "description": ("description", "desc", "\u63cf\u8ff0"),
    "group": ("group", "\u5206\u7ec4"),
    "has_visual": ("has_visual", "visual", "\u663e\u793a"),
    "conditions": ("conditions", "cond", "\u6761\u4ef6", "\u591a\u6761\u4ef6", "\u7ec4\u5408\u6761\u4ef6"),
    "notes": ("notes", "out_notes", "\u8f93\u51fa\u97f3\u7b26", "\u6309\u952e\u7ec4"),
    # 符号：数字编号（Cubase 符号模式）或任意文字（文本模式，见 model.normalize_symbol）
    "symbol": ("symbol", "\u8bb0\u8c31\u7b26\u53f7", "\u7b26\u53f7",
               "symbolcode", "\u7b26\u53f7\u7f16\u53f7"),
    "text": ("text", "\u77ed\u6807\u7b7e", "\u663e\u793a\u540d",
             "\u663e\u793a\u6587\u672c", "\u5c55\u793a\u6587\u672c"),
    # 显示方式：auto（自动）/ text（文本）/ symbol（符号）—— 给使用者看什么
    "display_mode": ("display", "display_mode", "displaymode",
                     "\u663e\u793a\u65b9\u5f0f", "\u663e\u793a\u65b9\u5f0f",
                     "\u5c55\u793a\u65b9\u5f0f", "\u7b26\u53f7/\u6587\u672c",
                     "displaytype"),
    "order": ("order", "\u987a\u5e8f", "index"),
    "map_name": ("map_name", "\u6620\u5c04\u540d", "\u8868\u60c5\u6620\u5c04"),
    "min_velocity": ("min_velocity", "minvelocity", "\u6700\u5c0f\u529b\u5ea6",
                     "\u529b\u5ea6\u4e0b\u9650"),
    "max_velocity": ("max_velocity", "maxvelocity", "\u6700\u5927\u529b\u5ea6",
                     "\u529b\u5ea6\u4e0a\u9650"),
    "articulationtype": ("articulationtype", "artictype", "\u8c31\u9762\u5f52\u7c7b",
                         "\u53d1\u97f3\u6cd5\u7c7b\u578b", "\u7c7b\u578b"),
    "min_pitch": ("min_pitch", "minpitch", "\u6700\u5c0f\u97f3\u9ad8"),
    "max_pitch": ("max_pitch", "maxpitch", "\u6700\u5927\u97f3\u9ad8"),
}


def _build_index(header):
    idx = {}
    norm = [h.strip().lower() if h else "" for h in header]
    for field_name, aliases in ALIASES.items():
        for a in aliases:
            if a in norm:
                idx[field_name] = norm.index(a)
                break
    return idx


def parse_csv(path: str) -> List[Art]:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    # utf-8-sig 兼容 Excel 导出的 BOM，退路用 GBK
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("无法解码 CSV（已试 utf-8-sig / utf-8 / gbk）: %s" % path)

    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("CSV 只有表头或为空: %s" % path)

    idx = _build_index(rows[0])
    if "name" not in idx:
        raise ValueError("CSV 缺少名称列（name / \u540d\u79f0 / \u6280\u6cd5）: %s" % rows[0])

    def cell(r, key, strip=True):
        """文本类字段（名称/描述）不能 strip，否则往返会丢首尾空格。"""
        i = idx.get(key)
        if i is None or i >= len(r):
            return ""
        v = r[i].replace("\r", "").replace("\n", "")
        return v.strip() if strip else v

    arts = []
    for n, r in enumerate(rows[1:], start=2):
        name = cell(r, "name", strip=False)
        # 名字可以留空 —— 整行都空的行上面已经滤掉了，剩下的空名行是「还没起名」，
        # 交给 model.dedupe_art_names 补成「插槽N」，别在这里悄悄丢掉整行。
        conds = decode_conditions(cell(r, "conditions", strip=False))
        sym = normalize_symbol(cell(r, "symbol"))
        txt = cell(r, "text", strip=False)
        atype = to_int(cell(r, "articulationtype"))
        mode = normalize_display_mode(cell(r, "display_mode"))
        if mode is None and (sym is None or isinstance(sym, str)):
            # 没写「显示方式」时，符号格有文字就顺手判成文本模式
            mode = "text" if isinstance(sym, str) else None
        if conds:
            # 单条件行的 symbol / text / 谱面归类从列上补进条件里
            # （组合行以 conditions 内编码为准）
            for c in conds:
                if c.symbol is None:
                    c.symbol = sym
                if not c.text:
                    c.text = txt
                if c.articulationtype is None:
                    c.articulationtype = atype
                if c.display_mode is None:
                    c.display_mode = mode
        a = Art(
            name=name,
            switch=norm_switch(cell(r, "switch") or None),
            note=parse_note(cell(r, "note")),
            note2=parse_note(cell(r, "note2")),
            channel=to_int(cell(r, "channel")),
            cc_num=to_int(cell(r, "cc_num")),
            cc_val=to_int(cell(r, "cc_val")),
            color=to_int(cell(r, "color")),
            length_fact=to_float(cell(r, "length_fact")),
            velocity_fact=to_float(cell(r, "velocity_fact")),
            transpose=to_int(cell(r, "transpose"), 0),
            min_velocity=to_int(cell(r, "min_velocity")),
            max_velocity=to_int(cell(r, "max_velocity")),
            remote=to_int(cell(r, "remote")),
            description=cell(r, "description", strip=False) or None,
            group=cell(r, "group", strip=False),
            order=to_int(cell(r, "order"), 0) or n,
            has_visual=to_bool(cell(r, "has_visual"), True),
            conditions=conds,
            notes=[parse_note(x) for x in cell(r, "notes").replace("\u3001", ",").split(",")
                   if parse_note(x) is not None],
            symbol=sym,
            text=txt,
            display_mode=mode,
            articulationtype=atype,
            min_pitch=to_int(cell(r, "min_pitch")),
            max_pitch=to_int(cell(r, "max_pitch")),
        )
        a._row = n
        arts.append(a)
    if not arts:
        raise ValueError("CSV 没有有效数据行: %s" % path)
    return arts


def map_name_from_csv(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
    else:
        return ""
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        return ""
    idx = _build_index(rows[0])
    if "map_name" in idx and idx["map_name"] < len(rows[1]):
        return rows[1][idx["map_name"]].strip()
    return ""
