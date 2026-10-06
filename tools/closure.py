# -*- coding: utf-8 -*-
"""
闭环验证（只读源文件）：
  真实 .expressionmap --dump--> CSV --build--> 新 .expressionmap
  再与原始文件逐字段比对。证明 CSV 是无损的、可反复迭代的。
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from em.reader import read_map              # noqa: E402
from em.renderer import render_map          # noqa: E402
from em.registry import get_brand           # noqa: E402
from em.parsers import parse_csv, map_name_from_csv  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = r"E:\Cubase project\模板文件\技法"
CSV_DIR = os.path.join(ROOT, "out", "csv_ref")
OUT = os.path.join(ROOT, "out", "_closure")
os.makedirs(OUT, exist_ok=True)

FIELDS = ("name", "switch", "note", "note2", "channel", "cc_num", "cc_val",
          "color", "length_fact", "velocity_fact", "transpose", "remote",
          "description", "has_visual", "min_velocity", "max_velocity",
          "min_pitch", "max_pitch")


def sig(a):
    """完整签名：字段 + 多条件 + 输出音符组。"""
    base = [getattr(a, f) for f in FIELDS]
    conds = tuple((int(c.group), c.description, c.symbol, c.text,
                   c.articulationtype) for c in a.conditions)
    return tuple(map(str, base)) + (conds, tuple(a.out_notes()))

brand = get_brand("kontakt")
ok, bad = 0, []

# Windows 文件名不允许尾空格，导出时会 strip，匹配时同样忽略
SRC_INDEX = {os.path.splitext(os.path.basename(p))[0].strip(): p
             for p in glob.glob(os.path.join(SRC, "*.expressionmap"))}

for csv_path in sorted(glob.glob(os.path.join(CSV_DIR, "*.csv"))):
    stem = os.path.splitext(os.path.basename(csv_path))[0]
    src_map = SRC_INDEX.get(stem.strip())
    if src_map is None:
        continue

    try:
        arts = parse_csv(csv_path)
        map_name = map_name_from_csv(csv_path)
        slots = brand.build_all(arts, brand.defaults)
        xml_text = render_map(map_name, slots)
        dst = os.path.join(OUT, stem + ".expressionmap")
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(xml_text)

        o_name, o_arts = read_map(src_map)
        n_name, n_arts = read_map(dst)
    except Exception as ex:
        bad.append((stem, "异常: %s" % ex))
        continue

    diffs = []
    if o_name != n_name:
        diffs.append("映射名 %r != %r" % (o_name, n_name))
    if len(o_arts) != len(n_arts):
        diffs.append("技法数 %d != %d" % (len(o_arts), len(n_arts)))
    for i, (a, b) in enumerate(zip(o_arts, n_arts), start=1):
        if sig(a) != sig(b):
            for fld in FIELDS:
                if getattr(a, fld) != getattr(b, fld):
                    diffs.append("#%d %s: %s=%r != %r"
                                 % (i, a.name, fld, getattr(a, fld), getattr(b, fld)))
                    break
            else:
                diffs.append("#%d %s: conds/notes\n       原 %r\n       新 %r"
                             % (i, a.name,
                                [(int(c.group), c.description, c.note, c.symbol,
                                  c.text, c.articulationtype) for c in a.conditions]
                                + [a.out_notes()],
                                [(int(c.group), c.description, c.note, c.symbol,
                                  c.text, c.articulationtype) for c in b.conditions]
                                + [b.out_notes()]))
    if diffs:
        bad.append((stem, diffs[:3]))
    else:
        ok += 1

print("=" * 68)
print("闭环验证（原 map -> CSV -> 新 map）")
print("无损通过: %d    有差异: %d" % (ok, len(bad)))
print("=" * 68)
for stem, d in bad:
    print("\n[差异] %s" % stem)
    if isinstance(d, list):
        for x in d:
            print("   " + str(x))
    else:
        print("   " + str(d))
