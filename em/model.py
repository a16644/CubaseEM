# -*- coding: utf-8 -*-
"""
统一中间层数据契约。
所有 parser / method / renderer 只认这里的结构 —— 模块之间唯一的公共语言。
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Union

# 切换方式
KS = "ks"          # 单 keyswitch
KS2 = "ks2"        # 双 keyswitch
CH = "ch"          # 纯通道
KS_CH = "ks+ch"    # 通道 + keyswitch
CC_MODE = "cc"     # MIDI CC
NONE = "none"      # 直通（不切换）

SWITCHES = (KS, KS2, CH, KS_CH, CC_MODE, NONE)
SWITCH_LABEL = {
    KS: "KeySwitch", KS2: "双KeySwitch", CH: "通道",
    KS_CH: "通道+KeySwitch", CC_MODE: "MIDI CC", NONE: "直通",
}

# MIDI 状态位
NOTE_ON = 144      # 0x90
CC_STATUS = 176    # 0xB0

DEFAULT_KS_VELOCITY = 120

# ---------------------------------------------------------------- 音名换算
# ⚠️ 八度编号没有统一标准，而 **Cubase 自己用的是「中央 C = C3」那一套**
#    （Steinberg 官方映射，音域 C-2 ~ G8）：
#        MIDI  0 = C-2      12 = C-1      24 = C0      36 = C1      60 = C3
#    科学记法（很多教材 / 别的 DAW）是「中央 C = C4」：24 = C1、60 = C4。
#    以前这里按科学记法算 —— 于是「软件里填 C0 → 导出进 Cubase 显示 C-1」，
#    整整差一个八度。现在默认跟 Cubase 对齐（OCTAVE_BASE = 2，
#    C0 = 24）；想要科学记法就把 octave_offset 设成 **-1**（OCTAVE_BASE 变 1）。
#    ⚠️ 两个方向（音名->号 / 号->音名）必须共用同一个基准，
#       各写一份公式迟早又会冒出「输入 C0 显示 C-1」。
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTAL = {"#": 1, "\u266f": 1, "b": -1, "\u266d": -1}
NOTE_NAME_RE = re.compile(r"^([A-Ga-g])([#b\u266f\u266d]?)(-?\d+)$")

OCTAVE_BASE = 2        # Cubase：n // 12 - 2 = 八度号（24 -> 0）
_OCTAVE_OFFSET = 0     # 用户校准，-1 = 科学记法（中央 C = C4，24 叫 C1）


def set_octave_offset(n) -> None:
    """整体平移音名的八度编号。

    -1 = 科学记法（24 叫 C1，中央 C = C4，也就是本工具以前的老叫法）
     0 = Cubase 默认（24 叫 C0，中央 C = C3）← 默认
    基准越大，同一个音名对应的 MIDI 号越高。
    """
    global _OCTAVE_OFFSET
    _OCTAVE_OFFSET = int(n or 0)


def get_octave_offset() -> int:
    return _OCTAVE_OFFSET


def octave_base() -> int:
    """音名 <-> MIDI 号共用的八度基准：解析时加它，显示时减它。"""
    return OCTAVE_BASE + _OCTAVE_OFFSET


def parse_note_name(s) -> int:
    """'C0' / 'c#-1' -> MIDI 号。默认按 Cubase 约定：C0 = 24。"""
    m = NOTE_NAME_RE.match(str(s).strip())
    if not m:
        raise ValueError("无法识别的音符: %r" % s)
    return ((int(m.group(3)) + octave_base()) * 12
            + PITCH_CLASS[m.group(1).upper()] + ACCIDENTAL.get(m.group(2), 0))


def midi_to_name(n) -> str:
    """MIDI 号 -> 音名。与 parse_note_name 严格互逆（同一个八度基准）。"""
    if n is None or str(n).strip() in ("", "-"):
        return "-"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "-"
    if n < 0:
        return "-"
    return "%s%d" % (NOTE_NAMES[n % 12], n // 12 - octave_base())

# 条件层：sv 的 group 0/1/2/3 = Cubase 界面里的 Art.1/2/3/4
MAX_GROUPS = 4
GROUP_LABEL = {0: "Art.1", 1: "Art.2", 2: "Art.3", 3: "Art.4"}

# 发音法「类型」——就是 Cubase「发音法」表格里那个下拉，也是 XML 的 articulationtype
#   0 = 属性       （作用于声音本身，比如连奏 / 拨弦）
#   1 = 奏法指示   （给演奏者看的提示，不影响出音）
ART_TYPE_ATTR = 0
ART_TYPE_PLAY = 1
ART_TYPE_LABEL = {ART_TYPE_ATTR: "属性", ART_TYPE_PLAY: "奏法指示"}
ART_TYPE_HINT = {
    ART_TYPE_ATTR: "作用于声音本身的条件，比如连奏、拨弦。多数技法选这个。",
    ART_TYPE_PLAY: "给演奏者看的指示，不影响出音。",
}


def parse_group(v) -> int:
    """把各种写法归一成 0-3。'1'/'Art.1'/'art1'/'组1' 都按 1-based 理解 -> 0。"""
    if v is None:
        return 0
    if isinstance(v, int):
        return max(0, min(MAX_GROUPS - 1, v))
    s = str(v).strip().lower()
    if not s:
        return 0
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return 0
    n = int(digits)
    # "0" 明确写作 0 时按 0-based 处理；其余按界面习惯 1-based
    if s in ("0", "group0", "g0", "art.0", "art0"):
        return 0
    if n >= 1:
        n -= 1
    return max(0, min(MAX_GROUPS - 1, n))


def group_label(g: int) -> str:
    return GROUP_LABEL.get(int(g), "Art.%d" % (int(g) + 1))


def clamp_group(v) -> int:
    """XML 里的 group 本身就是 0-based，直接夹到 0-3，不做 1-based 换算。"""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_GROUPS - 1, n))


def ev_note_on(note: int, vel: int = DEFAULT_KS_VELOCITY) -> Dict[str, int]:
    return {"status": NOTE_ON, "data1": int(note), "data2": int(vel)}


def ev_cc(num: int, val: int) -> Dict[str, int]:
    return {"status": CC_STATUS, "data1": int(num), "data2": int(val)}


# ---------------------------------------------------------------- 序列外推
def suggest_series(formulas: List[str], snapshots: List[Dict], lo: int = 0,
                   hi: int = 127) -> Dict:
    """按「只看下一个已知值」的规则，给出每一列空格该填什么。

    这是界面上那条**暗色提示**的计算来源，也是「一键补齐」的执行依据。

    formulas:
      已写好的格子，例如 ["24", "", "", "27", "28"] —— 空串代表没填。
    snapshots:
      每个格子的旁挂信息（switch / channel / cc_num…），用来判断哪些格子该参与外推：
        - 触发方式 = cc  → **永远跳过**（CC 必须人工填，你明确要求过）
        - 不是按键类的格子（常驻 / 纯通道）→ 由对应字段自己推，这里跳过
        - 组合行 → 输出是多个键的拼合，不参与单值外推

    返回：
      {
        "values":   {下标: 建议值},        # 暗色提示与一键补齐都用它
        "dir":      {下标: 1 或 -1},       # 1=递增 -1=递减，界面据此提示
        "from":     {下标: 锚点下标},
        "blocked":  {下标: 原因},          # 为什么这格不参与外推
      }
    """
    def usable(i: int) -> bool:
        snap = snapshots[i] if i < len(snapshots) else {}
        if snap.get("combo"):
            return False
        if str(snap.get("switch") or "") == CC_MODE:
            return False
        if snap.get("candidates") is False:   # 组合候选行等非独立槽位
            return False
        return True

    parsed = []
    for i, f in enumerate(formulas):
        s = str(f or "").strip()
        v = None
        if s and s.lstrip("+-").isdigit() and usable(i):
            v = int(s)
        parsed.append(v)

    values, dirs, frm, blocked = {}, {}, {}, {}
    for i in range(len(parsed)):
        if parsed[i] is not None:
            continue
        snap = snapshots[i] if i < len(snapshots) else {}
        if str(snap.get("switch") or "") == CC_MODE:
            blocked[i] = "CC 控制器要手动填，不自动推"
            continue
        if snap.get("combo"):
            blocked[i] = "组合行的输出由各层拼成，不单独推"
            continue
        # 只看下一个已知值（你的要求：不去看后面更远的）
        nxt = None
        for j in range(i + 1, len(parsed)):
            if parsed[j] is not None:
                nxt = (j, parsed[j])
                break
            if not usable(j):
                break        # 中间夹着不参与的格子，链子断了
        # 上一个已知值同样只看最近一个
        prv = None
        for j in range(i - 1, -1, -1):
            if parsed[j] is not None:
                prv = (j, parsed[j])
                break
            if not usable(j):
                break
        if prv is None or nxt is None:
            blocked[i] = "这一段的头或尾还没有填，填了就能接着推"
            continue
        vals = spread(prv[1], nxt[1], nxt[0] - prv[0] - 1)
        k = i - prv[0] - 1
        if 0 <= k < len(vals):
            values[i] = max(lo, min(hi, vals[k]))
            dirs[i] = 1 if nxt[1] >= prv[1] else -1
            frm[i] = prv[0]
    return {"values": values, "dir": dirs, "from": frm, "blocked": blocked}


def spread(prev: int, nxt: int, count: int, lo: int = 0, hi: int = 127) -> List[int]:
    """在 prev 与 nxt 之间插入 count 个值，返回这 count 个值。

    count=0 → []；count=1 → 取靠 prev 的那一格（递增时 = prev+1）。
    差额除不尽时余数摊在前面几格上，保证单调、不重复。
    lo / hi 是合法区间（音符 0~127，通道 1~16）。
    """
    if count <= 0:
        return []
    step = nxt - prev
    out = []
    for k in range(1, count + 1):
        # 用整数运算避免浮点误差：第 k 格 = prev + round(step * k / (count+1))
        num = step * k
        den = count + 1
        delta = int(round(num / den)) if num >= 0 else -int(round(-num / den))
        if delta == 0:
            # 差额太小摊不开：递增时至少 +1，递减时至少 -1，除非真的没得动
            delta = 1 if step > 0 else (-1 if step < 0 else 0)
        out.append(int(prev) + delta)
    # 夹到合法区间，并保证严格单调（同号时不允许重复）
    res = []
    for v in out:
        v = max(lo, min(hi, v))
        if res:
            if step > 0 and v <= res[-1]:
                v = res[-1] + 1
            elif step < 0 and v >= res[-1]:
                v = res[-1] - 1
            v = max(lo, min(hi, v))
        res.append(v)
    return res


def normalize_symbol(v) -> Optional[Union[int, str]]:
    """「符号」这一格怎么填都收：

    - 纯数字   -> int（Cubase 的符号编号，符号模式）
    - 其它文字 -> 原样保留成 str（文本模式，renderer 会写成 displaytype=1 + text）
    - 空       -> None

    以前只肯吃数字，写「滑音」「pizz.」会被静默丢掉——那是用户的常见写法，
    因为 Cubase 发音法面板里这一格本来就能填文本。"""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return s


DISPLAY_MODES = ("auto", "text", "symbol")


def normalize_display_mode(v) -> Optional[str]:
    """显示方式：auto / text / symbol，认中文与英文写法，别的（含空）返回 None = 自动。"""
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s:
        return None
    if s in ("t", "text", "1", "true", "y", "yes", "字符串", "文本", "文字",
             "文本显示", "文字显示", "显示文本", "文本模式"):
        return "text"
    if s in ("s", "symbol", "0", "false", "n", "no", "号", "符号",
             "符号显示", "符号模式", "显示符号"):
        return "symbol"
    return None


# ---------------------------------------------------------------- 槽位命名
# 没写名字的插槽一律叫「插槽N」（N = 它在表格里的序号），并且**全局不许重名**。
# 理由：写进 Cubase 的每个 slot 都靠名字认，两个同名条目在宿主的列表里
# 完全分不出谁是谁，用户回头根本没法改。所以生成前必须过一遍 make_unique_names。
SLOT_NAME_FMT = "插槽%d"


def default_slot_name(order: int) -> str:
    """第 order 个（1 开始）插槽的兜底名。"""
    return SLOT_NAME_FMT % int(order)


def make_unique_names(names, fmt: str = SLOT_NAME_FMT) -> List[str]:
    """把一串名字整理成「无空、无重名」。

    - 空名 / 纯空白 -> fmt % (序号+1)，即「插槽1」「插槽2」……
    - 重名 -> 从第 2 个起加 " (2)"、" (3)"…… 直到不撞为止
    - 已经唯一的名字原样保留（所以往返回归不受影响）
    """
    out: List[str] = []
    used = {}
    for i, raw in enumerate(names):
        n = ("" if raw is None else str(raw)).strip()
        if not n:
            n = fmt % (i + 1)
        if n in used:
            base = n
            k = used[base]
            while True:
                k += 1
                cand = "%s (%d)" % (base, k)
                if cand not in used:
                    break
            used[base] = k
            n = cand
        used[n] = 1
        out.append(n)
    return out


def dedupe_art_names(arts, fmt: str = SLOT_NAME_FMT) -> List[str]:
    """就地给一批 Art 补默认名并去重，返回**被改过的名字**列表（给界面提示用）。

    改名时连带把 description / 条件描述里"跟着名字走"的那份同步掉，
    否则左边「声音插槽」列和实际写入的名字会对不上。
    """
    fixed = make_unique_names([a.name for a in arts], fmt)
    changed: List[str] = []
    for a, new in zip(arts, fixed):
        old = (a.name or "").strip()
        if old == new:
            continue
        if not (a.description or "").strip() or a.description == a.name:
            a.description = new
        for c in (a.conditions or []):
            if not (c.description or "").strip() or c.description == a.name:
                c.description = new
        changed.append(new)
        a.name = new
    return changed


@dataclass
class Cond:
    """一个条件维度（Art.N 的一个取值）。组合槽位 = 多个不同 group 的 Cond。

    note = 该条件单独成立时发出的 keyswitch 音符；组合槽位的输出 = 各条件 note 的合集。

    纯展示字段（都不影响发声，也不影响 Cubase 的匹配逻辑）：
    text  = 界面上显示的短标签（displaytype=1 时用，否则显示 description）
    symbol = 记谱符号。**既可以填 Cubase 的符号编号（数字），也可以直接填文字**
    （见 normalize_symbol）——填文字就等价于"符号可以是文本"，renderer 会把它
    落成 displaytype=1 + text，使用者在 Cubase 发音法面板里看到的是这段文字。
    articulationtype = 谱面归类，0 或 1；跟 symbol 一样推断不出来，原样带着走

    display_mode = 显示方式（None/auto=自动，text=强制文本，symbol=强制符号）。
    只在显式选了 text / symbol 时才起作用，留空保持原样推断。
    """
    group: int = 0
    description: str = ""
    note: Optional[int] = None
    symbol: Optional[Union[int, str]] = None
    text: str = ""
    displaytype: Optional[int] = None
    articulationtype: Optional[int] = None
    display_mode: Optional[str] = None

    def to_dict(self) -> Dict:
        return {"group": int(self.group), "description": self.description,
                "note": self.note, "symbol": self.symbol,
                "text": self.text,
                "displaytype": (1 if self.text else self.displaytype),
                "articulationtype": self.articulationtype,
                "display_mode": self.display_mode}

    @staticmethod
    def from_dict(d: Dict) -> "Cond":
        n = d.get("note", None)
        dt = d.get("displaytype", None)
        at = d.get("articulationtype", None)
        return Cond(group=int(d.get("group", 0) or 0),
                    description=str(d.get("description", "") or ""),
                    note=None if n in ("",) else (None if n is None else int(n)),
                    symbol=normalize_symbol(d.get("symbol")),
                    text=str(d.get("text", "") or ""),
                    displaytype=None if dt in ("", None) else int(dt),
                    articulationtype=None if at in ("", None) else int(at),
                    display_mode=normalize_display_mode(d.get("display_mode")))


# ---- 多条件在 CSV 里的编码： "0:sus;1:正常" ----
COND_SEP = ";"
COND_KV = ":"


def encode_conditions(conds: List["Cond"]) -> str:
    out = []
# 组合行里每个条件还可能带 symbol / articulationtype，挂在同一个条件的末尾：
#   "0:sus;1:正常"                 基本写法（老 CSV 也认）
#   "0:sus~73~1;1:正常~210~1"      带上记谱符号与谱面归类
COND_EXTRA = "~"


def encode_conditions(conds: List["Cond"]) -> str:
    out = []
    for c in conds or []:
        d = (str(c.description).replace("\\", "\\\\")
             .replace(COND_SEP, "\\;").replace(COND_KV, "\\:")
             .replace(COND_EXTRA, "\\~"))
        seg = "%s%s%s" % (int(c.group), COND_KV, d)
        # 任一条带 symbol / articulationtype 才补尾巴，保证老 CSV 格式不变
        if c.symbol is not None or c.articulationtype is not None:
            # symbol 可能是文字（"符号可以是文本"），原样写回去，别硬转 int
            seg += COND_EXTRA + ("" if c.symbol is None else
                                 (c.symbol if isinstance(c.symbol, str)
                                  else str(int(c.symbol))))
            seg += COND_EXTRA + ("" if c.articulationtype is None
                                 else str(int(c.articulationtype)))
        out.append(seg)
    return COND_SEP.join(out)


def decode_conditions(text: str) -> List["Cond"]:
    if not text or not str(text).strip():
        return []
    res, buf, esc = [], [], False
    for ch in str(text):
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == COND_SEP:
            res.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    res.append("".join(buf))
    conds = []
    for item in res:
        sym = aty = None
        if COND_EXTRA in item:
            item, tail = item.split(COND_EXTRA, 1)
            parts = (tail.split(COND_EXTRA) + ["", ""])[:2]
            try:
                sym = normalize_symbol(parts[0])
                aty = int(parts[1]) if parts[1].strip() else None
            except ValueError:
                sym = aty = None
        if COND_KV not in item:
            continue
        g, d = item.split(COND_KV, 1)
        # unescape：encode_conditions 转义过的分隔符还原回来
        d = d.replace("\\" + COND_SEP, COND_SEP).replace("\\" + COND_KV, COND_KV) \
             .replace("\\" + COND_EXTRA, COND_EXTRA).replace("\\\\", "\\")
        # 这里的 group 由 encode_conditions 写成，是 0-based 原值，不做 1-based 换算
        conds.append(Cond(group=clamp_group(g), description=d,
                          symbol=sym, articulationtype=aty))
    return conds


@dataclass
class Art:
    """一条技法（用户视角，1-based 通道）。"""
    name: str
    switch: str = KS
    note: Optional[int] = None       # keyswitch 音符 0-127
    note2: Optional[int] = None      # 第二个 keyswitch
    channel: Optional[int] = None    # 通道 1-16
    cc_num: Optional[int] = None
    cc_val: Optional[int] = None
    color: Optional[int] = None      # 留空自动分配
    length_fact: float = 1.0         # 音符长度缩放
    velocity_fact: float = 1.0
    min_velocity: Optional[int] = None   # 力度窗口下限，留空写 0（不限制）
    max_velocity: Optional[int] = None   # 力度窗口上限，留空写 127
    transpose: int = 0
    min_pitch: Optional[int] = None      # 最小音高，留空写 0
    max_pitch: Optional[int] = None      # 最大音高，留空写 127
    remote: Optional[int] = None     # 远程触发键，-1 表示未分配
    description: Optional[str] = None
    group: str = ""
    order: int = 0
    has_visual: bool = True   # False = 该 slot 不带 USlotVisuals（样本中存在此类空槽）
    conditions: List[Cond] = field(default_factory=list)
    notes: List[int] = field(default_factory=list)  # 组合槽位要发的全部 keyswitch 音符
    symbol: Optional[Union[int, str]] = None        # 记谱符号（数字编号，或直接填文字）
    text: str = ""                                  # 界面短标签（给使用者看的那一段字）
    displaytype: Optional[int] = None               # 1 = 显示 text
    articulationtype: Optional[int] = None          # 谱面归类（0/1），原样带
    display_mode: Optional[str] = None              # auto/text/symbol，None = 自动

    def __post_init__(self):
        # conditions 是唯一真相；group / description 镜像第一条，保证老代码不掉队
        if self.conditions:
            self.sync_from_conditions()
        else:
            self.conditions = [Cond(parse_group(self.group),
                                    self.description or self.name,
                                    symbol=self.symbol,
                                    text=self.text,
                                    displaytype=self.displaytype,
                                    articulationtype=self.articulationtype,
                                    display_mode=self.display_mode)]

    def sync_from_conditions(self):
        if self.conditions:
            # 写回成 Art.N 标签，parse_group 能原样吃回去，避免 0/1-based 歧义
            self.group = group_label(self.conditions[0].group)
            self.description = self.conditions[0].description
            if len(self.conditions) == 1:
                self.articulationtype = self.conditions[0].articulationtype

    def set_conditions(self, conds: List[Cond]):
        self.conditions = list(conds or [Cond(0, self.name)])
        self.sync_from_conditions()

    def is_combo(self) -> bool:
        """组合槽位 = 同时满足两个以上条件层的槽。"""
        return len({int(c.group) for c in self.conditions}) > 1

    def out_notes(self) -> List[int]:
        """本槽要发出的 keyswitch 音符列表（组合槽 = 各条件音符合集）。"""
        if self.notes:
            return list(self.notes)
        ns = [c.note for c in self.conditions if c.note is not None]
        if len(ns) > 1:
            return ns
        out = []
        if self.note is not None:
            out.append(self.note)
        if self.note2 is not None:
            out.append(self.note2)
        return out

    def combo_label(self) -> str:
        return " + ".join("%s:%s" % (group_label(c.group), c.description or "?")
                          for c in self.conditions)

    def display_desc(self) -> str:
        return self.description or self.name


@dataclass
class SlotSpec:
    """渲染层输入（Cubase 视角，0-based 通道，-1 表示不指定）。"""
    name: str
    color: int
    channel: int = -1
    key: int = -1
    key2: Optional[int] = None
    controller_num: Optional[int] = None
    controller_val: Optional[int] = None
    messages: List[Dict[str, int]] = field(default_factory=list)
    length_fact: float = 1.0
    velocity_fact: float = 1.0
    transpose: int = 0
    remote: int = -1
    description: Optional[str] = None
    has_visual: bool = True
    conditions: List[Cond] = field(default_factory=list)
    # velocity 窗口：样本的绝大多数槽位是 0~127 全开，但 Shreddage 里有用
    # 70~90 卡力度分层的槽位 —— 这个是有实际作用的，必须原样带回去
    min_velocity: Optional[int] = None
    max_velocity: Optional[int] = None
    # 音高窗口，同理（样本多为 0~127，但 Cubase 界面里给的是两栏，要能改）
    min_pitch: Optional[int] = None
    max_pitch: Optional[int] = None

    @property
    def channel_display(self) -> str:
        return "-" if self.channel < 0 else str(self.channel + 1)

    @property
    def key_display(self) -> str:
        return "-" if self.key < 0 else str(self.key)

    def visual_list(self) -> List[Cond]:
        """渲染用：没有显式 conditions 时退回单条件。"""
        if self.conditions:
            return self.conditions
        return [Cond(0, self.description or self.name)]


@dataclass
class ExpressionMap:
    name: str
    arts: List[Art] = field(default_factory=list)
    brand: str = "kontakt"
