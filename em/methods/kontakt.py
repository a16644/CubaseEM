# -*- coding: utf-8 -*-
"""Kontakt / NI 系品牌模块。

Kontakt 常见两种布局：
  - 单实例多通道：每个技法占一个 MIDI 通道（ch / ks+ch）
  - 单通道 keyswitch：低音区音符切换（ks / ks2）
本模块只定义规则默认值，输出事件由基类统一构造。
"""
from .base import BrandModule


class Kontakt(BrandModule):
    id = "kontakt"
    display = "Kontakt / NI"
    defaults = {
        "keyswitch_base": 24,   # C1，Kontakt 库最常用的 keyswitch 起点
        "start_channel": 1,     # 多通道模板从第 1 通道起
        "ks_velocity": 120,
    }
