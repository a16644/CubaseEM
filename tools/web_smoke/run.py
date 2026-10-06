"""网页界面的无头浏览器冒烟测试。

用法：
    python tools/web_smoke/run.py            # 用默认端口 8777 / 9222
    python tools/web_smoke/run.py --app 8788

做什么：
1. 自己拉一个带调试端口的无头 Edge（用完关掉）
2. 用 Node 自带的 WebSocket 直连 CDP，跑 10 个用例（顺序固定，case_layout 必须最后）：
     case_ui.js      —— 缩放 / 键位推算 / 加一行 / 批量 / 类型 / 高级参数 / 导出目录
     case_note.js    —— 音名换算（含 128 音全量互逆，专防差八度）
     case_edit.js    —— 默认名 / 唯一化 / 同名文件确认 / 键盘导航 / MIDI 录键
     case_save.js    —— 保存撞键**只报不填**（用桩顶掉 api，不写真库）
     case_color_name.js —— 颜色六种改法
     case_pred_adv.js—— 分字段推算（CC / 细则参数）与「更多细则」面板跟随
     case_cc.js      —— CC 号 / CC 值 / 通道的**专用输入框** + 表格列宽可拖
     case_audit.js   —— 生成前审核按「触发部件」判定（键位 / 通道 / CC 都算）
     case_export.js  —— 打开导出文件夹，以及高级字段有没有真的写进 XML
     case_layout.js  —— 布局 / 按钮可点 /「退出程序」（点了会真退服务，排最后）

只依赖 Node（>=22，自带 WebSocket），不装 puppeteer 之类的第三方包。

⚠️ 无头模式下页面里的 confirm() 会卡死 JS，驱动里已经自动点「确定」，别去掉。
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import json

HERE = os.path.dirname(os.path.abspath(__file__))
EDGES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/microsoft-edge",
    "/usr/bin/google-chrome",
]


def find_node():
    for c in ("node", "node.exe"):
        p = shutil.which(c)
        if p:
            return p
    home = os.path.expanduser("~")
    base = os.path.join(home, r".workbuddy\binaries\node\versions")
    if os.path.isdir(base):
        for v in sorted(os.listdir(base), reverse=True):
            cand = os.path.join(base, v, "node.exe")
            if os.path.isfile(cand):
                return cand
    return None


def find_browser():
    for e in EDGES:
        if os.path.isfile(e):
            return e
    return None


def wait_cdp(port, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=1) as r:
                if json.load(r):
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=int, default=8777, help="网页工具端口")
    ap.add_argument("--cdp", type=int, default=9222, help="浏览器调试端口")
    ap.add_argument("--only", default="", help="只跑某一个用例，比如 case_note.js")
    args = ap.parse_args()

    node = find_node()
    if not node:
        print("找不到 node（要 >= 22，用来跑 WebSocket）")
        return 2
    browser = find_browser()
    if not browser:
        print("找不到 Edge / Chrome")
        return 2

    # 网页服务得先开着
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % args.app, timeout=2):
            pass
    except Exception:
        print("网页服务没起。先跑：python em/webapp.py --port %d" % args.app)
        return 2

    # ⚠️ case_layout 会点「退出程序」，那会把服务真的退掉（这是被测的行为本身）。
    #    所以每个用例开跑前先看一眼服务还在不在，不在就重新拉起来，
    #    否则后面三个用例会全挂在「页面打不开」上，看着像功能坏了。
    svc = [None]

    def service_alive():
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % args.app,
                                        data=b"{}", timeout=2):
                return True
        except Exception:
            return False

    def ensure_service():
        if service_alive():
            return
        print("    （上一个用例把服务退了，重新拉一个）")
        svc[0] = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "..", "..", "em", "webapp.py"),
             "--port", str(args.app), "--no-open", "--no-pin"],
            cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            if service_alive():
                return
            time.sleep(0.25)

    def stop_service():
        if svc[0] is not None:
            svc[0].kill()
            svc[0] = None

    # ⚠️ 配置目录必须**每次唯一**（带 pid + 时间戳）：
    #    上一轮如果被中断，会留下一个还开着的无头 Edge 和它的 profile；
    #    复用同名目录时，新 Edge 会「转交给已有实例」然后自己退出 ——
    #    既有 wait_cdp 一直起不来，开跑前那句 rmtree 也可能卡在锁住的文件上，
    #    整套测试就卡在**第一行输出之前**，什么日志都没有（踩过）。
    profile = os.path.join(os.environ.get("TEMP", "/tmp"),
                           "em_web_smoke_profile_%d_%d" % (os.getpid(), int(time.time())))
    print("无头浏览器 profile: %s" % profile, flush=True)
    proc = subprocess.Popen([
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        "--user-data-dir=" + profile,
        "--remote-debugging-port=%d" % args.cdp,
        "--remote-allow-origins=*", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_cdp(args.cdp):
        proc.kill()
        print("浏览器调试端口 %d 没起来（多半有残留的无头 Edge 占着，"
              "换个 --cdp 再试）" % args.cdp, flush=True)
        return 2

    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "em_export_smoke").replace("\\", "/")
    bad = 0
    try:
        env = dict(os.environ, CDP_PORT=str(args.cdp), APP_PORT=str(args.app),
                   SMOKE_TMP=tmp)
        # ⚠️ 顺序有讲究：case_layout 最后会点「退出程序」，那是**真的**把服务退掉
        #    （被测行为本身），点完页面就变成「程序已退出」，后面的用例没法接着跑。
        #    所以把会退服务的这个用例排到最后。
        order = ("case_ui.js", "case_note.js", "case_edit.js", "case_save.js",
                 "case_color_name.js", "case_pred_adv.js", "case_cc.js",
                 "case_audit.js", "case_export.js", "case_layout.js")
        if args.only:
            order = tuple(n for n in order if n == args.only) or (args.only,)
        for name in order:
            print("\n---- %s ----" % name, flush=True)
            ensure_service()
            r = subprocess.run([node, os.path.join(HERE, "cdp.js"),
                                os.path.join(HERE, name)],
                               cwd=HERE, env=env)
            if r.returncode:
                bad += 1
    finally:
        proc.kill()
        stop_service()

    # ⚠️ 结论先打出来，再收拾临时目录：
    #    删无头浏览器的 profile 偶尔会卡住（文件还被占着），
    #    以前把它放在 finally 里，卡住时连「全部通过」都看不到，看着像整套挂了。
    print("\n" + ("全部用例通过" if not bad else "有 %d 个用例失败" % bad), flush=True)
    # 清理放到 daemon 线程里等 10 秒：删不掉就让它自己烂在 TEMP 里，
    # 别为了一个临时目录把整个进程吊住。
    t = threading.Thread(target=lambda: shutil.rmtree(profile, ignore_errors=True),
                         daemon=True)
    t.start()
    t.join(10)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
