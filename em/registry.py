# -*- coding: utf-8 -*-
"""品牌模块自动发现：往 methods/ 丢一个实现 BrandModule 的 .py 即可，主程序零改动。"""
import importlib
import inspect
import os
import pkgutil
from .methods.base import BrandModule
from .methods import Kontakt

_CACHE = None

# PyInstaller 打包后 methods/ 里的 .py 已经被编译进 exe，磁盘上扫不到文件，
# `pkgutil.iter_modules` 会返回空 —— 表现是「只有 kontakt能用，加的品牌全丢」。
# 所以打包时靠 build.py 把实际存在的模块名写进这个环境变量，运行时直接读。
import os as _os
_ENV = _os.environ.get("CUBASEEM_BRANDS", "")


def _discover():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    mods = {"kontakt": Kontakt()}
    names = [n for n in _ENV.replace(",", ";").split() if n]
    if not names:
        # 源码模式：扫目录
        pkg_dir = _os.path.join(_os.path.dirname(__file__), "methods")
        for m in pkgutil.iter_modules([pkg_dir]):
            names.append(m.name)
    for name in names:
        if name in ("base", "__init__", "kontakt"):
            continue
        try:
            mod = importlib.import_module("em.methods." + name)
        except Exception:
            continue
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BrandModule) and obj is not BrandModule and getattr(obj, "id", None):
                mods[obj.id] = obj()
    _CACHE = mods
    return mods


def get_brand(brand_id: str) -> BrandModule:
    mods = _discover()
    if brand_id not in mods:
        raise KeyError("未知品牌 '%s'，可用: %s" % (brand_id, ", ".join(sorted(mods))))
    return mods[brand_id]


def list_brands():
    return _discover()
