# -*- coding: utf-8 -*-
"""探测 Cubase 的 Expression Maps 目录（只探测、只打印，绝不自动写入）。"""
import os

def candidates():
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    c = [
        os.path.join(docs, "Steinberg", "Cubase", "Expression Maps"),
        os.path.join(docs, "Steinberg", "Cubase 12", "Expression Maps"),
        os.path.join(home, "AppData", "Roaming", "Steinberg",
                     "Cubase 12_64", "Presets", "Expression Maps"),
        os.path.join(home, "AppData", "Roaming", "Steinberg",
                     "Cubase 15_64", "Presets", "Expression Maps"),
    ]
    return c


def existing():
    return [p for p in candidates() if os.path.isdir(p)]


def report():
    found = existing()
    if found:
        return "已发现的 Expression Maps 目录:\n" + "\n".join("  " + p for p in found)
    return ("未发现现成的 Expression Maps 目录。Cubase 12 通常在:\n  "
            + candidates()[0]
            + "\n（在 Cubase 里 Export Map 一次就会自动创建）")
