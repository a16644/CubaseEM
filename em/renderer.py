# -*- coding: utf-8 -*-
"""
把 SlotSpec 序列化成 Cubase 12 的 .expressionmap。

格式结论来自 25 个真实样本（326 个 slot）的字节级比对：
  - 3 空格/级缩进，CRLF 换行，文件末尾带换行
  - 根 <InstrumentMap>，成员顺序固定：name / slotvisuals / slots / controller
  - PSoundSlot 子元素顺序固定：remote / action / sv / name / color
  - ID 只需同一文件内唯一
"""
from typing import List
from .ids import IdGen
from .model import SlotSpec, Cond, normalize_display_mode

INDENT = "   "
HEADER = '<?xml version="1.0" encoding="utf-8"?>'


def esc(s: str) -> str:
    """属性值转义。样本里没出现过 & < >，但输入不可信，必须转义。"""
    return (str(s).replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;")
                  .replace('"', "&quot;"))


def fmt_float(v: float) -> str:
    """跟着 Cubase 的写法：整数就写整数（样本里 1.0 写成 "1"），
    小数写成 50 位小数再去掉尾零 —— 0.2 在样本里是
    0.2000000000000000111022302462515654042363166809082。
    用 Python 的 repr 只会得到 "0.2"，跟原文件对不上。"""
    f = float(v)
    if f.is_integer():
        return str(int(f))
    return ("%.50f" % f).rstrip("0")


def vel(v, default: int) -> int:
    """力度窗口：没指定就写 Cubase 的全开值（0 / 127）。"""
    return default if v is None else int(v)


def out_velocity(status: int, data2: int, s: "SlotSpec") -> int:
    """NoteOn 的力度会被裁进这个槽的力度窗口。

    Shreddage 有两个槽把窗口限成 70–90，原文里它们发出的 NoteOn 是 90，
    而不是默认的 120 —— 键位音符力度超窗口就会被夹到边界。
    默认窗口 0–127 时夹完还是原值，行为不变。
    """
    if status != 144:
        return data2
    lo = vel(s.min_velocity, 0)
    hi = vel(s.max_velocity, 127)
    if lo <= 0 and hi >= 127:
        return data2
    return max(lo, min(hi, data2))


class _W:
    """行缓冲，统一缩进与 CRLF。"""

    def __init__(self):
        self.buf: List[str] = []

    def line(self, depth: int, text: str):
        self.buf.append(INDENT * depth + text)

    def dump(self) -> str:
        return "\r\n".join(self.buf) + "\r\n"


def _visual_block(w: _W, depth: int, ids: IdGen, c):
    """一个 USlotVisuals。text/symbol/articulationtype 都是纯展示字段，不影响发声。

    displaytype 与 text 严格配对：有短标签就是 1，没有就是 0（25 份样本 100% 成立）。
    symbol 和 articulationtype 反过来——同一个 (层,描述) 在不同音源里取值不一样，
    推断不出来，只能原样带着走（新建的槽位默认 0 / 1）。

    两条补充规则（用户从 Cubase 发音法面板补的）：
    1. 「符号」这一格可以填文字，不只是编号。填了文字就当它 shouts 出显示文本——
       落进 <string name="text"> 并开 displaytype=1。Cubase 里这一列本来就有
       符号 / 文本 两选，左边声音插槽的名称是做表情的人看的，右边显示什么才是
       给用这个映射的人看的。
    2. display_mode=text 时，短标签没填就用技法名顶上，保证使用者看到的是字。
    """
    text = c.text or ""
    sym = c.symbol
    if isinstance(sym, str):
        # 文字型符号：它就是使用者看到的那段字（"符号可以是文本"）
        if sym.strip() and not text:
            text = sym.strip()
        sym = None
    elif sym is not None:
        sym = int(sym)

    mode = normalize_display_mode(c.display_mode) or "auto"
    if mode == "text" and not text:
        text = (c.description or "").strip()

    dtype = 1 if text else (0 if mode == "symbol" else (c.displaytype or 0))
    atype = c.articulationtype if c.articulationtype is not None else 1
    w.line(depth, '<obj class="USlotVisuals" ID="%d">' % ids.next())
    w.line(depth + 1, '<int name="displaytype" value="%d"/>' % int(dtype))
    w.line(depth + 1, '<int name="articulationtype" value="%d"/>' % int(atype))
    w.line(depth + 1, '<int name="symbol" value="%d"/>' % int(sym or 0))
    w.line(depth + 1, '<string name="text" value="%s" wide="true"/>' % esc(text))
    w.line(depth + 1, '<string name="description" value="%s" wide="true"/>' % esc(c.description))
    w.line(depth + 1, '<int name="group" value="%d"/>' % int(c.group))
    w.line(depth, "</obj>")


def render_map(map_name: str, slots: List[SlotSpec], seed: int = None, pool_order: List = None) -> str:
    ids = IdGen(seed)
    w = _W()
    w.line(0, HEADER)
    w.line(0, "<InstrumentMap>")
    w.line(1, '<string name="name" value="%s" wide="true"/>' % esc(map_name))

    # ---- slotvisuals：所有 sv 的展平去重池 ----
    # slotvisuals 池（一排 <? ... ?>：每个 = 一个可复用的 USlotVisuals）。
    # 实测 25 份真实文件里，池的顺序既不是按名称也不是按拼音，
    # 大多数是"第一次出现"的顺序（19/25），剩下 6 份是作者当年在 Cubase 里手点的杂乱顺序。
    # 所以：有新传进来的原始顺序就照抄（逐字节对齐），否则退回首次出现序。
    # 池的顺序只影响 Cubase 列表怎么显示，不影响发声。
    pool = {}
    for s in slots:
        if not s.has_visual:
            continue
        for c in s.visual_list():
            k = (c.description, int(c.group))
            if k not in pool:
                pool[k] = c
    ordered, seen = [], set()
    for c in pool_order or []:
        k = (c.description, int(c.group))
        if k in pool and k not in seen:
            ordered.append(pool[k])
            seen.add(k)
    ordered.extend(c for k, c in pool.items() if k not in seen)

    w.line(1, '<member name="slotvisuals">')
    w.line(2, '<int name="ownership" value="1"/>')
    w.line(2, '<list name="obj" type="obj">')
    for _c in ordered:
        _visual_block(w, 3, ids, _c)
    w.line(2, "</list>")
    w.line(1, "</member>")

    # ---- slots ----
    w.line(1, '<member name="slots">')
    w.line(2, '<int name="ownership" value="1"/>')
    w.line(2, '<list name="obj" type="obj">')
    for s in slots:
        _slot_block(w, 3, ids, s)
    w.line(2, "</list>")
    w.line(1, "</member>")

    # ---- controller（样本中恒为空壳）----
    w.line(1, '<member name="controller">')
    w.line(2, '<int name="ownership" value="1"/>')
    w.line(1, "</member>")
    w.line(0, "</InstrumentMap>")
    return w.dump()


def _slot_block(w: _W, depth: int, ids: IdGen, s: SlotSpec):
    w.line(depth, '<obj class="PSoundSlot" ID="%d">' % ids.next())

    # remote
    w.line(depth + 1, '<obj class="PSlotThruTrigger" name="remote" ID="%d">' % ids.next())
    w.line(depth + 2, '<int name="status" value="144"/>')
    w.line(depth + 2, '<int name="data1" value="%d"/>' % s.remote)
    w.line(depth + 1, "</obj>")

    # action
    w.line(depth + 1, '<obj class="PSlotMidiAction" name="action" ID="%d">' % ids.next())
    w.line(depth + 2, '<int name="version" value="600"/>')

    w.line(depth + 2, '<member name="noteChanger">')
    w.line(depth + 3, '<int name="ownership" value="1"/>')
    w.line(depth + 3, '<list name="obj" type="obj">')
    w.line(depth + 4, '<obj class="PSlotNoteChanger" ID="%d">' % ids.next())
    w.line(depth + 5, '<int name="channel" value="%d"/>' % s.channel)
    w.line(depth + 5, '<float name="velocityFact" value="%s"/>' % fmt_float(s.velocity_fact))
    w.line(depth + 5, '<float name="lengthFact" value="%s"/>' % fmt_float(s.length_fact))
    w.line(depth + 5, '<int name="minVelocity" value="%d"/>' % vel(s.min_velocity, 0))
    w.line(depth + 5, '<int name="maxVelocity" value="%d"/>' % vel(s.max_velocity, 127))
    w.line(depth + 5, '<int name="transpose" value="%d"/>' % s.transpose)
    w.line(depth + 5, '<int name="minPitch" value="%d"/>' % vel(s.min_pitch, 0))
    w.line(depth + 5, '<int name="maxPitch" value="%d"/>' % vel(s.max_pitch, 127))
    w.line(depth + 4, "</obj>")
    w.line(depth + 3, "</list>")
    w.line(depth + 2, "</member>")

    # 输出事件：0 条时只写 ownership（与纯通道 / 直通样本一致）
    w.line(depth + 2, '<member name="midiMessages">')
    w.line(depth + 3, '<int name="ownership" value="1"/>')
    if s.messages:
        w.line(depth + 3, '<list name="obj" type="obj">')
        for m in s.messages:
            w.line(depth + 4, '<obj class="POutputEvent" ID="%d">' % ids.next())
            w.line(depth + 5, '<int name="status" value="%d"/>' % m["status"])
            w.line(depth + 5, '<int name="data1" value="%d"/>' % m["data1"])
            w.line(depth + 5, '<int name="data2" value="%d"/>' % out_velocity(m["status"], m["data2"], s))
            w.line(depth + 4, "</obj>")
        w.line(depth + 3, "</list>")
    w.line(depth + 2, "</member>")

    w.line(depth + 2, '<int name="channel" value="%d"/>' % s.channel)
    w.line(depth + 2, '<float name="velocityFact" value="%s"/>' % fmt_float(s.velocity_fact))
    w.line(depth + 2, '<float name="lengthFact" value="%s"/>' % fmt_float(s.length_fact))
    w.line(depth + 2, '<int name="minVelocity" value="%d"/>' % vel(s.min_velocity, 0))
    w.line(depth + 2, '<int name="maxVelocity" value="%d"/>' % vel(s.max_velocity, 127))
    w.line(depth + 2, '<int name="transpose" value="%d"/>' % s.transpose)
    w.line(depth + 2, '<int name="maxPitch" value="%d"/>' % vel(s.max_pitch, 127))
    w.line(depth + 2, '<int name="minPitch" value="%d"/>' % vel(s.min_pitch, 0))
    if s.controller_num is not None:
        w.line(depth + 2, '<int name="controller1num" value="%d"/>' % s.controller_num)
        w.line(depth + 2, '<int name="controller1value" value="%d"/>' % (s.controller_val or 0))
    w.line(depth + 2, '<int name="key" value="%d"/>' % s.key)
    if s.key2 is not None:
        w.line(depth + 2, '<int name="key2" value="%d"/>' % s.key2)
    w.line(depth + 1, "</obj>")

    # sv（样本中存在不带 visual 的空槽，此时只写 ownership）
    w.line(depth + 1, '<member name="sv">')
    w.line(depth + 2, '<int name="ownership" value="2"/>')
    if s.has_visual:
        w.line(depth + 2, '<list name="obj" type="obj">')
        for c in s.visual_list():
            _visual_block(w, depth + 3, ids, c)
        w.line(depth + 2, "</list>")
    w.line(depth + 1, "</member>")

    # name / color
    w.line(depth + 1, '<member name="name">')
    w.line(depth + 2, '<string name="s" value="%s" wide="true"/>' % esc(s.name))
    w.line(depth + 1, "</member>")
    w.line(depth + 1, '<int name="color" value="%d"/>' % s.color)
    w.line(depth, "</obj>")
