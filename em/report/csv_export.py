# -*- coding: utf-8 -*-
"""反向导出：中间层 -> CSV（可再编辑、再生成，形成迭代闭环）。"""
import csv
import os
from typing import List
from ..model import Art, encode_conditions

HEADER = ["map_name", "name", "switch", "note", "note2", "channel",
          "cc_num", "cc_val", "color", "length", "velocity",
          "transpose", "remote", "description", "group", "order", "has_visual",
          "conditions", "notes", "symbol", "text", "display",
          "min_velocity", "max_velocity", "articulationtype",
          "min_pitch", "max_pitch"]


def write_csv(path: str, map_name: str, arts: List[Art]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for a in arts:
            w.writerow([
                map_name, a.name, a.switch,
                "" if a.note is None else a.note,
                "" if a.note2 is None else a.note2,
                "" if a.channel is None else a.channel,
                "" if a.cc_num is None else a.cc_num,
                "" if a.cc_val is None else a.cc_val,
                "" if a.color is None else a.color,
                a.length_fact, a.velocity_fact, a.transpose,
                "" if a.remote is None else a.remote,
                a.description or "", a.group, a.order,
                1 if a.has_visual else 0,
                encode_conditions(a.conditions),
                ",".join(str(n) for n in a.out_notes()),
                "" if a.symbol is None else a.symbol,
                a.text or "",
                # 显示方式：auto / text / symbol，留空 = 自动
                a.display_mode or "",
                "" if a.min_velocity is None else a.min_velocity,
                "" if a.max_velocity is None else a.max_velocity,
                "" if a.articulationtype is None else a.articulationtype,
                "" if a.min_pitch is None else a.min_pitch,
                "" if a.max_pitch is None else a.max_pitch,
            ])
    return path
