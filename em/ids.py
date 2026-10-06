# -*- coding: utf-8 -*-
"""ID 生成：样本验证结论 —— 同一文件内 ID 必须唯一，跨文件无所谓。"""
import random

LO = 1_000_000_000
HI = 99_999_999_999


class IdGen:
    def __init__(self, seed: int = None):
        self.rnd = random.Random(seed)
        self.used = set()

    def next(self) -> int:
        for _ in range(10000):
            v = self.rnd.randint(LO, HI)
            if v not in self.used:
                self.used.add(v)
                return v
        # 极端兜底：线性探测
        v = LO
        while v in self.used:
            v += 1
        self.used.add(v)
        return v
