# -*- coding: utf-8 -*-
"""
「双击 exe 之后到底发生了什么」—— 真跑 exe 才能验出来的几件事：

  A. 只开**一个**浏览器窗口（以前两处都调 _launch_browser，会开两个）
  B. 关掉浏览器窗口 → 程序自己退干净（子进程 + 启动器父进程 + 端口都没了）
  C. 已经有一个在跑时再双击 → 不起第二个窗口、不占第二个端口
  D. 关掉再双击 → 端口照常用回来，不会再弹「端口被占用」
  E. 手动点「退出程序」→ 进程立刻没

进程和窗口都直接用 Win32 接口数，不借 PowerShell（那玩意儿一次要一秒多，
会把「到底几秒退的」给糊弄过去）。

    python tools/check_gui_exit.py
"""
import os
import subprocess
import sys
import time
import urllib.request

import ctypes
from ctypes import wintypes

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_exe():
    """dist 下的 exe。

    打包出来的文件名可能带版本号后缀（比如 `表情映射生成器0.8.exe`），
    写死一个名字会「找不到 exe」的假失败 —— 先认默认名，
    找不到就取 dist 里**最新**的那个 exe。
    """
    import glob
    d = os.path.join(HERE, "dist")
    fixed = os.path.join(d, "表情映射生成器.exe")
    if os.path.isfile(fixed):
        return fixed
    cands = glob.glob(os.path.join(d, "*.exe"))
    return max(cands, key=os.path.getmtime) if cands else fixed


EXE = find_exe()
EXE_NAME = os.path.basename(EXE)                 # 任务管理器里看到的进程名
PORT = 8787
URL = "http://127.0.0.1:%d/" % PORT
TITLE = "表情映射编辑器"          # 界面页面的 <title>，也是浏览器窗口标题
PASS = FAIL = 0

# ---- Win32 ----
k32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def exe_pids():
    """还在跑的 exe 进程 —— 单文件模式是「启动器父进程 + Python 子进程」两个。"""
    out = []
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snap == -1:
        return out
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if k32.Process32First(snap, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.decode("gbk", "ignore") == EXE_NAME:
                    out.append(pe.th32ProcessID)
                if not k32.Process32Next(snap, ctypes.byref(pe)):
                    break
    finally:
        k32.CloseHandle(snap)
    return out


def _titles():
    got = []

    def enum(hwnd, _l):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value:
            got.append((hwnd, buf.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool,
                                          wintypes.HWND, wintypes.LPARAM)(enum), 0)
    return got


def browser_windows():
    """标题等于界面标题的窗口数 —— 就是用户看到的「几个页面」。
    ⚠️ 页面没加载完时标题还是 "127.0.0.1"，所以要看标题变成页面标题才算数。"""
    return len([1 for h, t in _titles() if t == TITLE])


def wait_window(seconds=25):
    end = time.time() + seconds
    while time.time() < end:
        if browser_windows() >= 1:
            return True
        time.sleep(0.5)
    return False


def close_browser_window():
    """真的去点那个窗口右上角 ×（发 WM_CLOSE）。"""
    for hwnd, t in _titles():
        if t == TITLE:
            user32.SendMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE（不是 0x0110，那是 WM_COMMAND）
            return True
    return False


def alive(pid):
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    code = wintypes.DWORD()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return bool(ok) and code.value == 259              # STILL_ACTIVE


def wait_gone(seconds=30):
    """等到 exe 一个进程都不剩（两种进程都算），返回实际秒数；超时返回 None。"""
    end = time.time() + seconds
    while time.time() < end:
        if not exe_pids():
            return 0.0
        time.sleep(0.5)
    return None


def port_alive(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port,
                                    data=b"{}", timeout=1.5):
            return True
    except Exception:
        return False


def wait_http(seconds=25):
    end = time.time() + seconds
    while time.time() < end:
        if port_alive(PORT):
            return True
        time.sleep(0.25)
    return False


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK]   %s %s" % (name, extra))
    else:
        FAIL += 1
        print("  [FAIL] %s %s" % (name, extra))


def cleanup():
    for pid in exe_pids():
        try:
            k32.TerminateProcess(k32.OpenProcess(0x0001, False, pid), 0)
            k32.CloseHandle(k32.OpenProcess(0x0001, False, pid))
        except Exception:
            pass
    for hwnd, t in _titles():
        if t == TITLE:
            user32.SendMessageW(hwnd, 0x0010, 0, 0)
    time.sleep(2)


def launch(extra_env=None):
    env = dict(os.environ)
    # 看门狗兜底（正常由「关窗口」触发的 beacon 立刻退出）。
    # 必须远大于心跳间隔(8s)，否则服务会被自己误判成「页面没了」而退出。
    env["CUBASEEM_AUTOCLOSE"] = "25"
    if extra_env:
        env.update(extra_env)
    env["CUBASEEM_LOGFILE"] = os.path.join(os.path.dirname(EXE), "_gui_exit.log")
    # DETACHED_PROCESS = 没有控制台（跟资源管理器里双击一模一样）。
    # 少了这个，sys.stdout 就不是 None，测不出「无控制台下 print 会炸」这类问题。
    return subprocess.Popen([EXE, "--port", str(PORT)],
                            env=env, cwd=os.path.dirname(EXE),
                            creationflags=0x00000008,               # DETACHED_PROCESS
                            stdin=subprocess.DEVNULL)


def main() -> int:
    if not os.path.isfile(EXE):
        print("找不到 %s —— 先跑 python build.py 打一个" % EXE)
        return 2

    print("=" * 62)
    print(" 真双击 exe：窗口数 / 退出 / 端口 全测一遍")
    print("=" * 62)

    cleanup()
    print("\n[A] 双击一次 —— 只该出现一个窗口")
    launch()
    ok("服务起来了", wait_http())
    ok("页面打开了", wait_window())
    ok("窗口数 == 1", browser_windows() == 1, "(实际 %d)" % browser_windows())
    ok("进程起来了", len(exe_pids()) == 2, "(%d 个)" % len(exe_pids()))

    print("\n[B] 关掉浏览器窗口 —— 程序必须真的退掉（含启动器父进程）")
    ok("找到窗口并点了 ×", close_browser_window())
    sec = wait_gone(30)
    ok("exe 进程全没了", sec is not None,
       "(%s)" % ("%.1f 秒" % sec if sec is not None else "30 秒后还在 %s" % exe_pids()))
    ok("端口 %d 也释放了" % PORT, not port_alive(PORT))

    print("\n[C] 已经有一个在跑时再双击 —— 不该冒出第二个")
    launch()
    if not wait_http() or not wait_window():
        ok("第一个起来", False)
        cleanup()
        return 1
    before = browser_windows()
    p2 = launch({"CUBASEEM_NO_GUI": "1"})         # 屏蔽那句提示弹窗，跑快点
    try:
        rc = p2.wait(timeout=25)
    except subprocess.TimeoutExpired:
        rc = None
    ok("第二个实例自己退了", rc == 0, "(返回码 %s)" % rc)
    time.sleep(2)
    ok("窗口数还是 1", browser_windows() == before == 1,
       "(%d → %d)" % (before, browser_windows()))
    ok("第一个还在服务", port_alive(PORT))
    ok("没多占 8788 端口", not port_alive(PORT + 1))

    print("\n[D] 手动点「退出程序」—— 立刻干净退出")
    try:
        urllib.request.urlopen(URL + "api/shutdown", data=b"{}", timeout=3)
    except Exception:
        pass
    sec = wait_gone(20)
    ok("进程全没了", sec is not None,
       "(%s)" % ("%.1f 秒" % sec if sec is not None else "20 秒后还在 %s" % exe_pids()))

    print("\n[E] 关掉后重新双击 —— 端口照常用回来")
    cleanup()
    launch()
    ok("重新双击能起", wait_http())
    ok("就用 8787（没被顶到 8788）", port_alive(PORT) and not port_alive(PORT + 1))
    cleanup()

    print("\n" + "=" * 62)
    print(" 通过 %d / 失败 %d" % (PASS, FAIL))
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
