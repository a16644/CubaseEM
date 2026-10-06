#!/usr/bin/env python3
"""在指定端口上拉一个无头 Edge 并跑一个用例脚本（开发时用）。

用法：
    python tools/web_smoke/debug_one.py case_ui.js
    python tools/web_smoke/debug_one.py _diag_cc.js --cdp 9345

⚠️ 配置目录必须**每次唯一**（带 pid + 时间戳）：
   上一次跑崩了（比如命令被中断）会留下 Edge 和 %TEMP%\\em_dbg_prof，
   复用同一个目录时新 Edge 会「转交给已有实例」然后自己退出 ——
   表现是调试端口一直起不来、node 端 send 永远不返回，看着像脚本卡死。
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def find_node():
    p = shutil.which("node") or shutil.which("node.exe")
    if p:
        return p
    base = os.path.join(os.path.expanduser("~"), r".workbuddy\binaries\node\versions")
    if os.path.isdir(base):
        for v in sorted(os.listdir(base), reverse=True):
            cand = os.path.join(base, v, "node.exe")
            if os.path.isfile(cand):
                return cand
    return None


def find_browser():
    for e in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if os.path.isfile(e):
            return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="?", default="case_layout.js")
    ap.add_argument("--app", default=os.environ.get("APP_PORT", "8777"))
    ap.add_argument("--cdp", default=os.environ.get("CDP_PORT", "9333"))
    a = ap.parse_args()

    node = find_node()
    edge = find_browser()
    if not node or not edge:
        print("找不到 node 或 Edge/Chrome")
        return 2

    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/state" % a.app, timeout=2):
            pass
    except Exception:
        print("网页服务没起。先跑：python em/webapp.py --port %s --no-open --no-pin" % a.app)
        return 2

    prof = os.path.join(os.environ.get("TEMP", "/tmp"),
                        "em_dbg_prof_%d_%d" % (os.getpid(), int(time.time())))
    p = subprocess.Popen([edge, "--headless=new", "--disable-gpu", "--no-first-run",
                          "--user-data-dir=" + prof,
                          "--remote-debugging-port=" + a.cdp,
                          "--remote-allow-origins=*", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok_port = False
    for _ in range(60):
        try:
            urllib.request.urlopen("http://127.0.0.1:%s/json/list" % a.cdp, timeout=1)
            ok_port = True
            break
        except Exception:
            time.sleep(0.3)
    if not ok_port:
        p.kill()
        print("浏览器调试端口 %s 没起来（多半是残留 Edge 占着 profile，换个 --cdp 再试）" % a.cdp)
        return 3

    env = dict(os.environ, CDP_PORT=a.cdp, APP_PORT=a.app,
               SMOKE_TMP=os.path.join(os.environ.get("TEMP", "/tmp"), "em_export_smoke"))
    try:
        r = subprocess.run([node, os.path.join(HERE, "cdp.js"), os.path.join(HERE, a.case)],
                           cwd=HERE, env=env, timeout=300)
        code = r.returncode
    except subprocess.TimeoutExpired:
        print("用例超时（>300s）")
        code = 4
    finally:
        p.kill()
        shutil.rmtree(prof, ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
