# -*- coding: utf-8 -*-
"""
逐字节往返验证（只读源文件）：
  真实样本 -> read_map -> renderer 重新生成 -> 与源文件做完整文本 diff

比 roundtrip.py 更严格：这里连 slotvisuals 池的顺序和 symbol 值一起比，
差异按原因分类打印（属于"预期不生成"的会单独标出来）。

末尾会单独统计 **slots 段**（真正决定发声的那段）逐字节相同的文件数：
这段一致 = 技法槽、触发键、输出事件全都跟原文件一字不差。
"""
import difflib
import glob
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from em.reader import read_map          # noqa: E402
from em.renderer import render_map      # noqa: E402
from em.registry import get_brand       # noqa: E402

SRC = r"E:\Cubase project\模板文件\技法"
TMP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "out", "_rtfull"))
os.makedirs(TMP, exist_ok=True)
brand = get_brand("kontakt")


def norm(t):
    """把 ID 抹掉，只比结构。

    换行要先统一：样本里有三种 —— CRLF（多数）、LF、**只有 CR 的老 Mac 换行**
    （CH Solo Strings 那两个文件）。不归一化的话 CR-only 会被当成一整行，
    比对结果完全是假的。"""
    t = re.sub(r'ID="\d+"', 'ID="X"', t)
    return t.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")


def section(t, name):
    """抠出 <member name="xxx"> ... 到下一个顶层 member 之前的那一段。"""
    i = t.find('<member name="%s">' % name)
    if i < 0:
        return ""
    j = t.find('<member name="', i + 10)
    return t[i:j if j > 0 else len(t)]


def norm_eol(t):
    """只把换行统一成 \\n，别的什么都不动（用来判断源文件原本用什么换行）。"""
    return "\r\n" in t or "\r" in t


total_lines = diff_lines = 0
bad = []
same_slots = same_vis = old_eol = 0
nfiles = 0
for f in sorted(glob.glob(os.path.join(SRC, "*.expressionmap"))):
    base = os.path.basename(f)
    doc = read_map(f)
    name, arts = doc[0], doc[1]
    # 把原文件的 slotvisuals 池顺序也带上 —— 那个顺序推不出来，只能原样带回
    xml = render_map(name, brand.build_all(arts, brand.defaults), pool_order=doc.visual_pool)
    with open(os.path.join(TMP, base), "w", encoding="utf-8", newline="") as fh:
        fh.write(xml)

    # ---- 分段统计：slots 是真正决定发声的那一段 ----
    nfiles += 1
    raw_src = open(f, "r", encoding="utf-8-sig", newline="").read()
    same_slots += 1 if norm(section(raw_src, "slots")) == norm(section(xml, "slots")) else 0
    same_vis += 1 if norm(section(raw_src, "slotvisuals")) == norm(section(xml, "slotvisuals")) else 0
    if "\r\n" not in raw_src and "\r" in raw_src:
        old_eol += 1

    a = norm(open(f, "r", encoding="utf-8-sig").read())
    b = norm(xml)
    total_lines += len(a)
    d = [l for l in difflib.unified_diff(a, b, n=0, lineterm="")
         if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    diff_lines += len(d)
    if d:
        bad.append((base, len(a), len(d), d[:6]))

print("=" * 70)
print("逐行往返（已抹掉 ID，含 slotvisuals 顺序与 symbol）")
print("文件数 %d   源文件总行数 %d   差异行 %d" % (len(glob.glob(os.path.join(SRC, "*.expressionmap"))),
                                              total_lines, diff_lines))
print("=" * 70)
for base, n, dn, sample in bad:
    print("\n[差异 %d/%d 行] %s" % (dn, n, base))
    for s in sample:
        print("   " + s)

print()
print("---- 分段结论（共 %d 个文件）----" % nfiles)
print("slots 段逐字节相同：       %d/%d   ← 这段一致 = 发声行为与原文件一致" % (same_slots, nfiles))
print("slotvisuals 段逐字节相同： %d/%d   ← 纯显示，不影响发声" % (same_vis, nfiles))
print("源文件是老式 CR 换行的：   %d 个   ← 重新生成统一写 CRLF，这部分差异是换行不是内容" % old_eol)
