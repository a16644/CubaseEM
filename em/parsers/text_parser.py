# -*- coding: utf-8 -*-
"""
从音源界面 / PDF 说明书复制的乱文本解析。

能识别的常见写法：
    C1 Legato          Legato - C1        C#1: Staccato
    24 Legato          Legato  (C1)       ch2 Legato
    ch2 C1 Legato      通道2 Legato       [CH3] Pizz
解析不出来的行不会被丢弃，而是标记出来让你人工校正。
"""
import re
from typing import List, Tuple
from ..model import Art, KS, KS2, CH, KS_CH, NONE
from .common import parse_note

CH_RE = re.compile(r"\[?\s*(?:ch|CH|Ch|\u901a\u9053)\s*(\d{1,2})\s*\]?")
NOTE_NAME_RE = re.compile(r"\b([A-Ga-g][#b\u266f\u266d]?-?\d+)\b")
NUM_RE = re.compile(r"\b(\d{1,3})\b")
SEP_RE = re.compile(r"^[\s\-\u2013\u2014:|\uFF1A,.\u3001\u3002()\[\]{}\t]+|"
                    r"[\s\-\u2013\u2014:|\uFF1A,.\u3001\u3002()\[\]{}\t]+$")


def _clean(s: str) -> str:
    s = s.strip()
    prev = None
    while prev != s:
        prev = s
        s = SEP_RE.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def parse_text(text: str, default_switch: str = KS) -> Tuple[List[Art], List[str]]:
    """default_switch: 没识别到音符/通道的行按什么处理，默认 ks（后续自动补键）。"""
    arts, warns = [], []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 明显的标题/表头行跳过
        if re.fullmatch(r"[\-\u2013=_\s]+", line):
            continue

        channel = None
        m = CH_RE.search(line)
        if m:
            channel = int(m.group(1))
            line = line.replace(m.group(0), " ")

        note = None
        mn = NOTE_NAME_RE.search(line)
        if mn:
            try:
                note = parse_note(mn.group(1))
                line = line.replace(mn.group(0), " ")
            except ValueError:
                pass
        if note is None:
            for mnum in NUM_RE.finditer(line):
                v = int(mnum.group(1))
                if 0 <= v <= 127:
                    note = v
                    line = line.replace(mnum.group(0), " ")
                    break

        name = _clean(line)
        if not name:
            warns.append("第 %d 行解析不出技法名，已跳过: %r" % (lineno, raw))
            continue

        if channel and note is not None:
            switch = KS_CH
        elif channel:
            switch = CH
        elif note is not None:
            switch = KS
        else:
            switch = default_switch
            if default_switch == NONE:
                warns.append("第 %d 行未识别到音符/通道，按直通处理: %r" % (lineno, raw))
            else:
                warns.append("第 %d 行未识别到音符/通道，已按 %s 处理并自动补键: %r"
                             % (lineno, default_switch, raw))

        arts.append(Art(name=name, switch=switch, note=note, channel=channel,
                        order=len(arts) + 1))
    return arts, warns


def parse_text_file(path: str, default_switch: str = KS):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return parse_text(f.read(), default_switch)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("无法解码文本文件: %s" % path)
