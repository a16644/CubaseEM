# -*- coding: utf-8 -*-
"""解析器共用工具：音名换算、切换方式归一化。"""
import re
from ..model import (KS, KS2, CH, KS_CH, CC_MODE, NONE,
                     parse_note_name, midi_to_name,      # noqa: F401  转发
                     set_octave_offset, get_octave_offset,
                     octave_base, OCTAVE_BASE)


def parse_note(v):
    """'C0' / 'C#0' / 24 / '24' / '' -> int 或 None。

    ⚠️ 默认按 **Cubase 的约定**：C0 = 24（中央 C = C3 = 60）。
    和 midi_to_name 共用同一个八度基准，怎么改都不会自己打自己。
    """
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "None"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return parse_note_name(s)


_SWITCH_ALIAS = {
    "ks": KS, "keyswitch": KS, "key": KS, "k": KS,
    "\u952e\u4f4d": KS, "\u6309\u952e": KS, "\u97f3\u7b26": KS, "\u952e": KS,
    "ks2": KS2, "\u53cc\u952e": KS2, "\u53cc\u97f3": KS2,
    "ch": CH, "channel": CH, "\u901a\u9053": CH,
    "ks+ch": KS_CH, "ks_ch": KS_CH, "ch+ks": KS_CH,
    "\u901a\u9053+\u952e": KS_CH, "\u901a\u9053+\u97f3\u7b26": KS_CH,
    "cc": CC_MODE, "midicc": CC_MODE,
    "none": NONE, "\u76f4\u901a": NONE, "\u65e0": NONE, "": KS,
}


def norm_switch(v) -> str:
    if v is None:
        return KS
    s = str(v).strip().lower().replace(" ", "")
    if s in _SWITCH_ALIAS:
        return _SWITCH_ALIAS[s]
    raise ValueError("无法识别的切换方式: %r（可用 ks / ks2 / ch / ks+ch / cc / none）" % v)


def to_int(v, default=None):
    if v is None:
        return default
    s = str(v).strip()
    if s in ("", "-", "None"):
        return default
    return int(float(s))


def to_bool(v, default=True) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("", "-", "none"):
        return default
    return s in ("1", "true", "yes", "y", "on")


def to_float(v, default=1.0):
    if v is None:
        return default
    s = str(v).strip()
    if s in ("", "-", "None"):
        return default
    return float(s)
