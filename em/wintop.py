# -*- coding: utf-8 -*-
"""
窗口置顶（Windows / ctypes，不装任何第三方包）。

把标题里带 APP_TITLE 的窗口设为 HWND_TOPMOST —— 效果跟任务管理器的"置于顶层"一样，
压在所有软件上面，切到 Cubase 里试听时输入框不会被盖住。
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time

APP_TITLE = "\u8868\u60c5\u6620\u5c04\u7f16\u8f91\u5668"   # 表情映射编辑器

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040

_user32 = None
IS_WIN = hasattr(ctypes, "windll")
_KEEP = {"on": False, "thread": None}   # 置顶看门狗


def _u32():
    """64 位下必须显式声明 argtypes：HWND 是指针宽度，
    交给 ctypes 默认转换会只填低 32 位，HWND_TOPMOST(-1) 就传错了。"""
    global _user32
    if _user32 is None and IS_WIN:
        u = ctypes.windll.user32
        u.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
        u.EnumWindows.restype = ctypes.c_bool
        u.IsWindowVisible.argtypes = [wt.HWND]
        u.IsWindowVisible.restype = ctypes.c_bool
        u.GetWindowTextLengthW.argtypes = [wt.HWND]
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wt.HWND, ctypes.c_wchar_p, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u.SetWindowPos.restype = ctypes.c_bool
        u.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
        u.ShowWindow.restype = ctypes.c_bool
        u.SetForegroundWindow.argtypes = [wt.HWND]
        u.SetForegroundWindow.restype = ctypes.c_bool
        u.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
        u.GetAncestor.restype = wt.HWND
        _user32 = u
    return _user32


def _root(hwnd):
    """往上找到顶层祖先 —— Chromium 的 --app 窗口有时把置顶样式挂在父窗口上。"""
    u = _u32()
    if not u:
        return []
    GA_ROOT = 2
    chain, guard = [hwnd], 0
    cur = u.GetAncestor(hwnd, GA_ROOT)
    while cur and cur not in chain and guard < 8:
        chain.append(cur)
        cur = u.GetAncestor(cur, GA_ROOT)
        guard += 1
    return chain


def find_windows(sub=APP_TITLE):
    """枚举可见窗口，返回标题包含 sub 的 [(hwnd, title)]。"""
    u = _u32()
    if not u:
        return []
    out = []
    prot = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(hwnd, _l):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 2)
        u.GetWindowTextW(hwnd, buf, n + 2)
        title = buf.value
        if sub and sub.lower() in title.lower():
            out.append((hwnd, title))
        return True

    u.EnumWindows(prot(cb), 0)
    return out


def set_topmost(hwnd, on=True):
    u = _u32()
    if not u:
        return False
    u.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                   0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    return True


def bring_front(hwnd):
    u = _u32()
    if not u:
        return False
    try:
        u.ShowWindow(hwnd, 9)          # SW_RESTORE
        u.SetForegroundWindow(hwnd)
    except Exception:
        pass
    return True


def _style_flag(hwnd) -> bool:
    u = _u32()
    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 0x00000008
    try:
        return bool(u.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
    except Exception:
        return False


def _apply(hwnd, on: bool):
    """连同顶层祖先一起设，返回是否真的生效（按样式位回读为准）。"""
    ok = False
    for h in _root(hwnd):
        set_topmost(h, on)
        if _style_flag(h):
            ok = True
    return ok


def stop_watch(timeout: float = 3.0):
    """停掉置顶看门狗并把窗口真正放下来。"""
    _KEEP["on"] = False
    t = _KEEP.get("thread")
    if t is not None and t.is_alive() and t is not threading.current_thread():
        t.join(timeout)
    _KEEP["thread"] = None
    for hwnd, _ in find_windows():
        for h in _root(hwnd):
            set_topmost(h, False)
    return True


def _watch(sub=APP_TITLE, gap: float = 2.0):
    """保持顶层：页面刷新导致窗口重建、或被别的软件抢走时会自动拉回来。"""
    while _KEEP["on"]:
        try:
            for hwnd, _ in find_windows(sub):
                _apply(hwnd, True)
        except Exception:
            pass
        time.sleep(gap)


def pin(on=True, sub=APP_TITLE, keep: bool = True):
    """置顶 / 取消置顶所有匹配窗口，返回命中的标题列表。"""
    if not on:
        stop_watch()
        return [t for _, t in find_windows(sub)]

    hits = find_windows(sub)
    for hwnd, _ in hits:
        _apply(hwnd, True)
        bring_front(hwnd)
    if keep:
        if not (_KEEP.get("thread") and _KEEP["thread"].is_alive()):
            _KEEP["on"] = True
            th = threading.Thread(target=_watch, args=(sub,), daemon=True)
            _KEEP["thread"] = th
            th.start()
    return [t for _, t in hits]


def pinned(sub=APP_TITLE):
    """当前是否处于置顶状态（有匹配窗口且样式带 WS_EX_TOPMOST）。"""
    return bool(state(sub)["windows"] and any(state(sub)["detail"].values()))


def state(sub=APP_TITLE) -> dict:
    """给界面用的完整状态：拿到几个窗口、各自当前是不是真的在最上层。"""
    hits = find_windows(sub)
    detail = [{"title": t, "topmost": _style_flag(h)} for h, t in hits]
    return {
        "found": len(hits),
        "windows": [t for _, t in hits],
        "detail": {("%d" % i): d["topmost"] for i, d in enumerate(detail)},
        "list": detail,
        "pinned": any(d["topmost"] for d in detail),
        "keep_running": bool(_KEEP.get("thread") and _KEEP["thread"].is_alive()),
    }


def _cli():
    """命令行入口：python em/wintop.py on|off|status"""
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    arg = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if arg in ("on", "1", "top", "pin"):
        hits = pin(True)
        print("已置顶: %s" % (hits or "（没找到编辑器窗口，先启动网页工具）"))
    elif arg in ("off", "0", "unpin"):
        hits = pin(False)
        print("已取消置顶: %s" % (hits or "（没找到编辑器窗口）"))
    else:
        st = state()
        print("置顶状态: %s" % ("开" if st["pinned"] else "关"))
        print("匹配窗口: %s" % (st["windows"] or "无"))
        print("逐个回读: %s" % (st["list"] or "无"))
        print("看门狗:   %s" % ("运行中" if st["keep_running"] else "未运行"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
