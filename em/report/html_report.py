# -*- coding: utf-8 -*-
"""可视化对照表：技法名 / 切换方式 / 通道 / 按键 / CC / 颜色 一页看完。"""
import html
import os
from typing import List
from ..model import Art, SWITCH_LABEL
from ..parsers.common import midi_to_name

# Cubase 调色板（样本中 color 为 1-16 的索引），仅用于对照表着色
PALETTE = ["#7f7f7f", "#c0392b", "#e67e22", "#f1c40f", "#2ecc71", "#1abc9c",
           "#3498db", "#9b59b6", "#e91e63", "#795548", "#607d8b", "#d35400",
           "#16a085", "#8e44ad", "#cddc39", "#00bcd4"]


def _swatch(idx: int) -> str:
    if idx is None or idx < 1:
        return "#bdc3c7"
    return PALETTE[(idx - 1) % len(PALETTE)]


def write_html(path: str, map_name: str, arts: List[Art], brand: str,
               notes: List[str] = None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    rows = []
    for i, a in enumerate(arts, start=1):
        color = a.color or 1
        rows.append(
            "<tr>"
            "<td class='idx'>%d</td>"
            "<td><span class='sw' style='background:%s'></span></td>"
            "<td class='nm'>%s</td>"
            "<td>%s</td>"
            "<td class='mono'>%s</td>"
            "<td class='mono'>%s</td>"
            "<td class='mono'>%s</td>"
            "<td class='desc'>%s</td>"
            "</tr>" % (
                i, _swatch(color), html.escape(a.name),
                html.escape(SWITCH_LABEL.get(a.switch, a.switch)),
                "-" if a.channel is None else "CH%d" % a.channel,
                "-" if a.note is None else "%d (%s)" % (a.note, midi_to_name(a.note)),
                "-" if a.cc_num is None else "CC%d=%s" % (a.cc_num, a.cc_val),
                html.escape(a.description or ""),
            ))

    note_html = ""
    if notes:
        note_html = ("<h2>生成说明</h2><ul class='notes'>%s</ul>"
                     % "".join("<li>%s</li>" % html.escape(n) for n in notes))

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>%s — 表情映射对照表</title>
<style>
body{font-family:"Microsoft YaHei",-apple-system,Segoe UI,sans-serif;background:#f7f8fa;
     color:#1f2329;margin:0;padding:32px}
.wrap{max-width:1040px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;
      border-radius:10px;padding:28px 32px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#6b7280;font-size:13px;margin-bottom:20px}
h2{font-size:15px;margin:24px 0 10px;color:#374151}
table{border-collapse:collapse;width:100%%;font-size:13px}
th{background:#f3f4f6;text-align:left;padding:9px 10px;color:#4b5563;
   border-bottom:1px solid #e5e7eb;font-weight:600}
td{padding:8px 10px;border-bottom:1px solid #f0f1f3}
tr:hover td{background:#fafbfc}
.idx{color:#9ca3af;width:44px}
.nm{font-weight:600}
.mono{font-family:Consolas,Monaco,monospace}
.desc{color:#6b7280}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:middle}
.notes{margin:0;padding-left:20px;color:#6b7280;font-size:13px;line-height:1.9}
</style></head><body><div class="wrap">
<h1>%s</h1>
<div class="sub">共 %d 条技法 · 品牌模块 %s · Cubase 12 表情映射</div>
<table><thead><tr><th>#</th><th>色</th><th>技法</th><th>切换方式</th>
<th>通道</th><th>按键</th><th>CC</th><th>描述</th></tr></thead>
<tbody>%s</tbody></table>
%s
</div></body></html>
""" % (html.escape(map_name), html.escape(map_name), len(arts),
       html.escape(brand), "".join(rows), note_html)

    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path
