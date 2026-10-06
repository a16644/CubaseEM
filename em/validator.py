# -*- coding: utf-8 -*-
"""生成前校验：把 Cubase 里极难排查的冲突提前抓出来。"""
from typing import List, Tuple
from .model import Art, KS, KS2, CH, KS_CH, CC_MODE


def validate(arts: List[Art]) -> Tuple[List[str], List[str]]:
    """返回 (errors, warnings)。errors 建议阻断生成。"""
    errors, warns = [], []
    seen_name, seen_note, seen_ch, seen_cc = {}, {}, {}, {}

    for i, a in enumerate(arts, start=1):
        tag = "#%d %s" % (i, a.name)

        if not a.name.strip():
            errors.append("%s: 技法名为空" % tag)

        if a.switch not in (KS, KS2, CH, KS_CH, CC_MODE, "none"):
            errors.append("%s: 未知的切换方式 '%s'" % (tag, a.switch))

        # 名称重名
        if a.name in seen_name:
            warns.append("%s: 技法名与 #%d 重复" % (tag, seen_name[a.name]))
        else:
            seen_name[a.name] = i

        # 数值范围
        for label, v, lo, hi in (("音符", a.note, 0, 127), ("第二音符", a.note2, 0, 127),
                                 ("通道", a.channel, 1, 16), ("CC号", a.cc_num, 0, 127),
                                 ("CC值", a.cc_val, 0, 127), ("移调", a.transpose, -127, 127)):
            if v is not None and not (lo <= v <= hi):
                errors.append("%s: %s=%s 超出范围 %d~%d" % (tag, label, v, lo, hi))

        # 必填项
        if a.switch in (KS, KS2, KS_CH) and a.note is None:
            errors.append("%s: 切换方式需要 keyswitch 音符但未指定" % tag)
        if a.switch == KS2 and a.note2 is None:
            warns.append("%s: 双 keyswitch 方式但第二音符未指定" % tag)
        if a.switch in (CH, KS_CH) and a.channel is None:
            errors.append("%s: 切换方式需要通道但未指定" % tag)
        if a.switch == CC_MODE and a.cc_num is None:
            errors.append("%s: CC 方式但未指定 CC 号" % tag)

        # 冲突
        # 撞车只警告不阻断：真实库里确实存在多技法共用一个 keyswitch 的情况
        if a.note is not None:
            key = (a.channel or 0, a.note)
            if key in seen_note:
                warns.append("%s: keyswitch 音符 %d 与 #%d 相同（同通道组）"
                             % (tag, a.note, seen_note[key]))
            else:
                seen_note[key] = i
        if a.channel is not None:
            if a.channel in seen_ch and a.switch == CH:
                warns.append("%s: 通道 CH%d 与 #%d 相同（纯通道模式下一技法一通道）"
                             % (tag, a.channel, seen_ch[a.channel]))
            seen_ch.setdefault(a.channel, i)
        if a.cc_num is not None:
            key = (a.cc_num, a.cc_val)
            if key in seen_cc:
                warns.append("%s: CC%d=%s 与 #%d 完全相同" % (tag, a.cc_num, a.cc_val, seen_cc[key]))
            else:
                seen_cc[key] = i

    return errors, warns
