# -*- coding: utf-8 -*-
"""品牌模块基类：只写规则层，事件构造交给共享工具，避免每个品牌重复造轮子。"""
from typing import List, Dict
from ..model import (Art, SlotSpec, KS, KS2, CH, KS_CH, CC_MODE, NONE,
                     ev_note_on, ev_cc, midi_to_name, spread as _spread)

NEED_NOTE = (KS, KS2, KS_CH)
NEED_CHANNEL = (CH, KS_CH)

_note_name = midi_to_name   # 日志里的音名，跟界面/对照表用同一套换算


class BrandModule:
    id = "base"
    display = "通用"
    # 规则层默认参数，可被 CSV 显式值或 CLI 覆盖
    defaults: Dict = {
        "keyswitch_base": 24,   # C1
        "start_channel": 1,
        "ks_velocity": 120,
    }
    capabilities = (KS, KS2, CH, KS_CH, CC_MODE, NONE)

    def build(self, art: Art, cfg: Dict = None) -> SlotSpec:
        """Art -> SlotSpec（1-based 通道转 0-based，未指定为 -1）。"""
        cfg = cfg or {}
        vel = int(cfg.get("ks_velocity", self.defaults.get("ks_velocity", 120)))
        sw = art.switch
        channel = (art.channel - 1) if art.channel else -1
        # 组合槽位：输出 = 各条件音符合集（3 个以上条件也能发，key/key2 只记录前两个）
        notes = art.out_notes()
        key = notes[0] if notes else -1
        k2 = notes[1] if len(notes) > 1 else None
        messages = []
        cnum = cval = None

        if sw in (KS, KS_CH) and key >= 0:
            messages = [ev_note_on(n, vel) for n in notes]
        elif sw == KS2:
            messages = [ev_note_on(n, vel) for n in notes]
        elif sw == CC_MODE:
            cnum, cval = art.cc_num, art.cc_val
            if cnum is not None:
                messages = [ev_cc(cnum, art.cc_val or 0)]

        return SlotSpec(
            name=art.name,
            color=art.color or 1,
            channel=channel if channel >= 0 else -1,
            key=key,
            key2=k2 if sw in (KS2, KS, KS_CH) else None,
            controller_num=cnum,
            controller_val=cval,
            messages=messages,
            length_fact=art.length_fact,
            velocity_fact=art.velocity_fact,
            transpose=art.transpose,
            min_velocity=art.min_velocity,
            max_velocity=art.max_velocity,
            min_pitch=art.min_pitch,
            max_pitch=art.max_pitch,
            remote=art.remote if art.remote is not None else -1,
            description=art.display_desc(),
            has_visual=art.has_visual,
            conditions=list(art.conditions),
        )

    def autofill(self, arts: List[Art], cfg: Dict = None,
                 fill_triggers: bool = True) -> List[str]:
        """按品牌规则补齐未填的 note / channel / color，返回补全说明。

        「补齐」分两轮，第二轮才轮到这里的顺序递推：
          1. 界面上已经写好的键位 / 通道，是**锚点**，不动
          2. 锚点之间空着的位置，按「只看下一个锚点」的规则外推（递增/递减）
          3. 还是没填上的，才从起始键往后找第一个没被占用的
        这样你手填的那几个键永远优先，「若干个切换区域各按各的规律」也能各自成立。

        fill_triggers=False（网页界面上的「自动补触发键」没打开）时**一个触发部件都不碰**：
        触发键 / 第二键 / 通道留空就留空，生成出来是 key=-1 + 通道 / CC 那套 ——
        也就是「按通道切换」的纯通道触发，不会凭空多出一个要按的键。
        颜色这类渲染必需的默认值照补（renderer 要的是整数，缺了会炸）。
        """
        cfg = cfg or {}
        flat_notes = set(n for a in arts for n in a.out_notes())
        chans = set(a.channel for a in arts if a.channel is not None)
        next_note = int(cfg.get("keyswitch_base", self.defaults["keyswitch_base"]))
        next_ch = int(cfg.get("start_channel", self.defaults["start_channel"]))
        log = []
        # 没指定颜色的行**跟随上一行**（第一个是 1）。
        # 不要在这里搞递增 / 随机换色 —— 界面上有专门的「颜色…」模块做这件事，
        # 命令行这条路上同理，默认是「跟着走」，不是「换个新的」。
        prev_color = 1
        color_filled = 0

        # ---- 第 2 轮：锚点之间的递推（只作用在触键类 + 非 CC 的行上）----
        # 这轮也算「补触发键」，开关关掉时一起跳过。
        for fld, pool, is_note in ((("note", flat_notes, True),
                                    ("channel", chans, False))
                                   if fill_triggers else ()):
            idx = [i for i, a in enumerate(arts)
                   if self._pool_ok(arts[i], fld, cfg)]
            vals = [(i, getattr(arts[i], fld)) for i in idx]
            anchors = [(i, v) for i, v in vals if v is not None]
            if len(anchors) < 2:
                continue
            for k in range(len(anchors) - 1):
                (i0, v0), (i1, v1) = anchors[k], anchors[k + 1]
                gap = [i for i in idx if i0 < i < i1
                       and getattr(arts[i], fld) is None]
                if not gap:
                    continue
                hi = 127 if is_note else 16
                vals_fill = _spread(v0, v1, len(gap), lo=1 if not is_note else 0,
                                    hi=hi)
                for i, v in zip(gap, vals_fill):
                    setattr(arts[i], fld, v)
                    log.append("按前后键位递推 %s: %s -> %s" % (
                        "触发键" if is_note else "通道", arts[i].name,
                        _note_name(v) if is_note else "CH%d" % v))

        # ---- 第 3 轮：真正没锚点的，顺序补空位 ----
        # 前三个 if 都是「补触发部件」—— 开关关掉时整段跳过；
        # 颜色 / remote 是渲染必需的默认值，任何时候都要补。
        would_fill = 0
        for i, a in enumerate(arts):
            if not fill_triggers:
                if ((a.switch in NEED_NOTE and a.note is None and not a.out_notes())
                        or (a.switch == KS2 and a.note2 is None)
                        or (a.switch in NEED_CHANNEL and a.channel is None)):
                    would_fill += 1
            if fill_triggers and a.switch in NEED_NOTE and a.note is None and not a.out_notes():
                while next_note in flat_notes:
                    next_note += 1
                a.note = next_note
                flat_notes.add(next_note)
                log.append("自动补 keyswitch 音符: %s -> %d" % (a.name, a.note))
            if fill_triggers and a.switch == KS2 and a.note2 is None:
                if a.conditions and len(a.conditions) > 1:
                    miss = [c for c in a.conditions if c.note is None]
                    for c in miss:
                        while next_note in flat_notes:
                            next_note += 1
                        c.note = next_note
                        flat_notes.add(next_note)
                    if miss:
                        log.append("组合槽补键: %s -> %s" % (
                            a.name, "+".join(str(c.note) for c in a.conditions if c.note is not None)))
                else:
                    while next_note in flat_notes:
                        next_note += 1
                    a.note2 = next_note
                    flat_notes.add(next_note)
                    log.append("自动补第二 keyswitch: %s -> %d" % (a.name, a.note2))
            if fill_triggers and a.switch in NEED_CHANNEL and a.channel is None:
                while next_ch in chans:
                    next_ch += 1
                a.channel = next_ch
                chans.add(next_ch)
                log.append("自动补通道: %s -> CH%d" % (a.name, a.channel))
            if a.color is None:
                a.color = prev_color
                color_filled += 1
            prev_color = a.color
            if a.remote is None:
                a.remote = -1
        if would_fill:
            log.append("「自动补触发键」关着：%d 行触发键 / 通道空着，按原样生成"
                       "（不补键位，靠通道 / CC 触发；要补就在「更多设置」里打开它）"
                       % would_fill)
        if color_filled:
            log.append("没写颜色的 %d 行跟随上一行的颜色（第一行是 1）；"
                       "想整批换色用网页界面的「颜色…」模块" % color_filled)
        return log

    # ---- 递推参与资格：CC 一律不参与（必须人工填），组合行也不参与 ----
    @staticmethod
    def _pool_ok(a: Art, fld: str, cfg: Dict) -> bool:
        if a.switch == CC_MODE:
            return False
        if a.is_combo():
            return False
        if fld == "note":
            return a.switch in NEED_NOTE
        return a.switch in NEED_CHANNEL

    def build_all(self, arts: List[Art], cfg: Dict = None) -> List[SlotSpec]:
        return [self.build(a, cfg) for a in arts]
