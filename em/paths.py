# -*- coding: utf-8 -*-
"""
路径自举：不管代码放在哪、是不是被冻结成 exe，目录都能自己长出来。

两种运行形态
------------
1. **源码运行**（`python em/webapp.py`）
   根 = 本文件上溯两级的项目目录，里面有 em/ config/ out/。
2. **打包运行**（PyInstaller 冻结的 exe）
   PyInstaller 有两种模式，路径含义完全不同：
   - **onedir**（默认）：exe 旁边有一堆 `_internal/`，只读资源在里面。
     根 = exe 所在目录 → `out/` `config/` 会落在 exe 旁边，绿色便携。
   - **onefile**（单文件）：运行时把资源解压到 `%TEMP%/_MEIxxxx`，
     那个目录**每次运行都不一样、而且退出就被删**，绝不能往那儿写东西。
     所以根仍然取 **exe 所在目录**，只有「读资源」才用解压目录。

为什么不用 %APPDATA%
--------------------
这个工具是绿色便携的：拷贝到 U 盘、放到 D 盘、换台机器都能直接双击用。
配置和产出跟着 exe 走，卸载 = 删文件夹，不留垃圾。

写不进去怎么办
--------------
exe 被塞进 `C:\\Program Files` 或别的只读位置时，`config/` 会写失败。
这时自动回退到 `%LOCALAPPDATA%\\CubaseEM`，并在界面上说明白搬到哪儿了。
"""
import os
import sys

# ---------------------------------------------------------------- 冻结判定
FROZEN = bool(getattr(sys, "frozen", False))   # PyInstaller 会注入这个属性

APP_NAME = "CubaseEM"
APP_TITLE = "表情映射生成器"


def is_frozen() -> bool:
    return FROZEN


def app_root() -> str:
    """**可写**的根目录：用户的配置和产出都放这儿。

    源码模式 = 项目目录；冻结模式 = exe 所在目录（绝不是 _MEI 临时目录）。
    """
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    # 源文件是 em/paths.py，上溯两级才是项目根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def res_dir() -> str:
    """**只读**资源的根：index.html 这类随包走的文件。

    onefile 模式下必须用 `sys._MEIPASS`（PyInstaller 把资源解压到了那里）；
    源码和 onedir 模式下就是项目根。
    """
    if FROZEN:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return base
        return app_root()
    return app_root()


# ---------------------------------------------------------------- 目录
class _Dirs(dict):
    """惰性字典：第一次取某个键时才去建目录。"""

    def __missing__(self, key):
        d = self._spec()[key]()
        os.makedirs(d, exist_ok=True)
        self[key] = d
        return d

    @staticmethod
    def _spec():
        root = app_root()
        return {
            "root": lambda: root,
            "out": lambda: os.path.join(root, "out"),
            "config": lambda: os.path.join(root, "config"),
            "libs": lambda: os.path.join(root, "config", "libs"),
            "data": lambda: os.path.join(root, "data"),
            "upload": lambda: os.path.join(root, "out", "_upload"),
        }


D = _Dirs()

# 常用别名（保持和以前一样的名字，别的地方 import 起来不用改）
ROOT = D["root"]
OUT_DIR = D["out"]
CONFIG_DIR = D["config"]
DATA_DIR = D["data"]


def out_dir() -> str:
    """产物目录 = 当前配置的导出目录（可能已被用户改成 Cubase 的目录）。"""
    try:
        import json
        p = os.path.join(CONFIG_DIR, "settings.json")
        with open(p, "r", encoding="utf-8") as f:
            raw = (json.load(f) or {}).get("out_dir") or ""
    except (OSError, ValueError):
        return OUT_DIR
    raw = str(raw).strip()
    if not raw:
        return OUT_DIR
    if not os.path.isabs(raw):
        raw = os.path.join(ROOT, raw)
    return os.path.abspath(raw)


def web_dir() -> str:
    """界面文件所在目录。"""
    return os.path.join(res_dir(), "em", "web")


def resource(*parts) -> str:
    """拼一个只读资源的完整路径（给 index.html 之类用）。"""
    return os.path.join(res_dir(), *parts)


def writable_root() -> str:
    """确认根目录真的能写。

    `C:\\Program Files` 这种位置建目录会直接 `PermissionError`。
    真写不进去就搬到 `%LOCALAPPDATA%\\CubaseEM`，宁可换地方也不能让程序起不来。
    """
    global D
    root = app_root()
    probe = os.path.join(root, "config")
    try:
        os.makedirs(probe, exist_ok=True)
        # 真的写一下 —— 只 makedirs 成功不代表有写权限（目录可能是别人建的只读）
        # 自动化脚本（tools/verify_exe.py）会设这个变量：只想确认路径可写，
        # 不想真的落一个探针文件又删掉它 —— 那样在受限环境里会被拦下。
        if os.environ.get("CUBASEEM_NO_WRITE_PROBE"):
            return root
        t = os.path.join(probe, ".wtest")
        try:
            with open(t, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(t)          # 删不掉也不影响「这里能写」这个结论
        except Exception:
            pass                  # 任何原因删不掉都算过（这个探针的意义是「能不能写」）
        return root
    except OSError:
        fallback = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
        os.makedirs(os.path.join(fallback, "config"), exist_ok=True)
        D = _Dirs()          # 换掉缓存，让后续取到的都是新根
        D["root"] = fallback
        _note_fallback(fallback)
        return fallback


_FALLBACK_NOTED = {"done": False}


def _note_fallback(path: str) -> None:
    """只提示一次，别刷屏。"""
    if _FALLBACK_NOTED["done"]:
        return
    _FALLBACK_NOTED["done"] = True
    try:
        _say("程序所在位置不能写入，配置与产物已改放到：\n  %s" % path)
    except Exception:
        pass


def _say(msg: str) -> None:
    """frozen 成 GUI 程序后 sys.stdout 可能是 None，不能假设它存在。"""
    out = getattr(sys, "stdout", None)
    if out is not None:
        try:
            out.reconfigure(encoding="utf-8")   # 控制台是 GBK 时中文不炸
        except Exception:
            pass
        print(msg)
    # 排错后门：CUBASEEM_LOGFILE=<路径> 时把说的话另存一份。
    # 双击 exe 没有控制台，出了事只能靠这个文件看。
    log = os.environ.get("CUBASEEM_LOGFILE")
    if log:
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass


def ensure_dirs() -> str:
    """开服务前调一次：把要用到的目录全建出来，返回真正生效的根。"""
    root = writable_root()
    for k in ("out", "config", "libs", "data", "upload"):
        D[k]
    return root


def describe() -> str:
    """给 `--doctor` / 启动横幅用：让人一眼看出程序认哪儿。"""
    return "\n".join([
        "运行方式: %s" % ("打包的 exe" if FROZEN else "Python 源码"),
        "根目录  : %s" % D["root"],
        "产物目录: %s" % out_dir(),
        "配置文件: %s" % CONFIG_DIR,
        "界面文件: %s" % web_dir(),
        "只读资源: %s" % res_dir(),
    ])
