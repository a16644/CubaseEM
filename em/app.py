# -*- coding: utf-8 -*-
"""
单文件入口 —— 打包成 exe 后双击的就是这个。

跟 `em/webapp.py` 的区别只有三点，都是为了「像个正式软件」：
  1. 端口被占用时自动往后找（8777 → 8778 → …），不给用户看报错
  2. 出错时弹窗告知，而不是让黑窗口一闪就没（GUI 模式下没有控制台）
  3. 关掉服务有明确说法：没有控制台可按 Ctrl+C，所以给一个「停止」的办法

命令行参数仍然全部支持，方便做快捷方式或者排错：
    程序.exe --port 9000 --no-open --no-pin --no-gui
"""
import argparse
import os
import sys
import threading
import time
import webbrowser

# 冻结后 em 包就在 exe 里，直接 import；源码模式要把项目根加进 path
if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from em import paths                                    # noqa: E402
from em import webapp                                   # noqa: E402


def _pick_port(want: int, tries: int = 30) -> int:
    """端口被占用就往后顺延。

    分享给别人之后最常见的场景就是「他电脑上已经有一个在跑了」
    （或者你自己开了两个），这时不该弹一堆错，应该自己换个号。

    ⚠️ 探测时**不能**设 SO_REUSEADDR —— Windows 上这个选项允许绑定
    一个已被 LISTENING 占用的端口，探测会「通过」，然后 serve 立刻失败。
    这里就是要拿到真实的占用状态，所以什么都不设。
    """
    import socket
    for p in range(want, want + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return want          # 全占了就用原来的，交给 serve 报错，至少有提示


def _msgbox(title: str, text: str, fatal: bool = False) -> None:
    """弹窗提示。GUI 模式下没有控制台，print 等于什么都看不见。"""
    paths._say("%s\n%s" % (title, text))
    if os.environ.get("CUBASEEM_NO_GUI"):      # 给自动化测试留后门
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if fatal else 0x40)
    except Exception:
        pass


def _open_in_thread(url: str) -> None:
    def run():
        time.sleep(0.4)          # 等服务真的 listening
        try:
            webapp._launch_browser(url)
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def _instance_alive(want: int, tries: int = 3) -> int:
    """这个端口上是不是**已经有一个本程序在跑**？是的话返回那个端口。

    只看端口占用是不够的——占用可能是别的程序（Skype、远程桌面…）。
    所以要真发一个 /api/ping，答「pong」的才是我们自己的实例。

    找到就说明：用户又双击了一次。正确做法是把浏览器带到**已有的那个**实例上，
    自己立刻退出（别再占第二个端口、别再弹「端口被占用」的框）。
    """
    import urllib.request
    for p in range(want, want + tries):
        try:
            req = urllib.request.Request("http://127.0.0.1:%d/api/ping" % p,
                                         data=b"{}", method="POST")
            with urllib.request.urlopen(req, timeout=0.6) as r:
                if r.status == 200:
                    return p
        except Exception:
            continue
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Cubase 表情映射生成器")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-open", action="store_true", help="不自动开浏览器")
    ap.add_argument("--no-pin", action="store_true", help="不自动置顶")
    ap.add_argument("--no-gui", action="store_true", help="出错时用控制台输出而不是弹窗")
    ap.add_argument("--doctor", action="store_true", help="打印路径信息后退出")
    ap.add_argument("--self-test", action="store_true",
                    help="不启服务，只自检能否生成文件（打包后的冒烟用）")
    a = ap.parse_args()

    if a.no_gui:
        os.environ["CUBASEEM_NO_GUI"] = "1"

    root = paths.ensure_dirs()

    if a.doctor:
        print(paths.describe())
        return 0

    if a.self_test:
        return self_test(root, a.no_gui)

    # 先问一句：已经有一个本程序在跑吗？
    living = _instance_alive(a.port)
    if living:
        # 已有实例在跑 → 本次什么都不启：既不开第二个浏览器窗口（那就会出现
        # 两个一模一样的界面），也不再占第二个端口、不弹「端口被占用」。
        # 用户看到的就是一句提示，关掉它剩下的就是已经在用的那个界面。
        _msgbox(paths.APP_TITLE,
                "已经有程序在运行（端口 %d），\n"
                "界面已经在浏览器里开着，直接用就行。\n\n"
                "要开新的就先把现在这个窗口关掉。" % living)
        return 0

    port = _pick_port(a.port)
    if port != a.port:
        _msgbox(paths.APP_TITLE,
                "端口 %d 已被占用，本次改用 %d。" % (a.port, port))

    def serve():
        try:
            # ⚠️ open_browser=False：浏览器由下面的 _open_in_thread 开**一次**就好。
            #    以前两处都开，双击 exe 会看到两个一模一样的窗口。
            #    auto_exit=True：关掉浏览器窗口即使服务真的退出，不再赖着占端口。
            webapp.start(port, False, not a.no_pin, auto_exit=True)
        except OSError as ex:
            _msgbox(paths.APP_TITLE,
                    "服务启动失败：%s\n\n请把程序换个位置（比如桌面或 D 盘）再试。" % ex,
                    fatal=True)
        except Exception as ex:                     # 兜底，别让窗口静默消失
            import traceback
            _msgbox(paths.APP_TITLE, "出了个没预料到的问题：\n%s" % ex, fatal=True)
            paths._say(traceback.format_exc())

    if a.no_open:
        return serve()

    # GUI 模式：不能在主线程跑 serve_forever（会挡住消息循环），
    # 也不能直接 serve —— 没有控制台时用户不知道怎么关。
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    url = "http://127.0.0.1:%d/" % port
    # ?ac=1 = 「这是 exe 自己打开的窗口」，页面只在这种时候做关窗自动退出。
    # 不加这个标记，用户把地址输到普通浏览器标签里、跳去别的网页就会把服务退掉。
    _open_in_thread(url + "?ac=1")
    # ⚠️ 这几句中文别挪回 .bat 里去写：cmd 在「chcp 65001 + UTF-8 无 BOM 的 bat」
    #    下会把中文行读成乱码命令（'XXecho' is not recognized），bat 因此静默挂掉。
    #    bat 保持纯 ASCII，要说的话全交给 Python 打。
    paths._say("=" * 56)
    paths._say("  %s 已启动" % paths.APP_TITLE)
    paths._say("  浏览器会自动打开，窗口会压在最上面。")
    paths._say("  端口被占用会自动换一个。")
    paths._say("  地址: %s" % url)
    paths._say("  目录: %s" % root)
    paths._say("  停止: 在这个窗口按 Ctrl+C，或直接关掉这个窗口")
    paths._say("  提示: 只是想用的话，双击 dist 里的 exe 就行，不需要 Python。")
    paths._say("=" * 56)
    try:
        while t.is_alive():
            t.join(0.5)
    except KeyboardInterrupt:
        pass
    return 0


def self_test(root: str, quiet: bool = False) -> int:
    """打包后的冒烟：不启服务，直接生成一个文件试试水。

    用来在**没有 Python 的机器上**验证「exe 里的代码和资源是不是齐的」。
    """
    import tempfile
    from em.model import Art
    from em.registry import get_brand
    from em.renderer import render_map
    from em.reader import read_map
    try:
        brand = get_brand("kontakt")
        art = Art(name="自检 Legato", switch="ks", note=24, channel=1, color=1)
        brand.autofill([art], dict(brand.defaults))
        xml = render_map("自检映射", brand.build_all([art], dict(brand.defaults)))
        tmp = os.path.join(tempfile.gettempdir(), "_cubaseem_selftest.expressionmap")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(xml)
        name, back = read_map(tmp)
        web = paths.web_dir()
        idx = os.path.join(web, "index.html")
        ok = (name == "自检映射" and len(back) == 1 and os.path.isfile(idx))
        detail = ("生成 %d 字节 / 回读 %d 条 / 界面文件 %d 字节"
                  % (len(xml.encode("utf-8")), len(back), os.path.getsize(idx)))
        os.remove(tmp)
        if not quiet:
            _msgbox(paths.APP_TITLE,
                    ("自检通过\n\n%s\n\n根目录：%s" % (detail, root)) if ok
                    else ("自检**失败**\n\n%s" % detail), fatal=not ok)
        print("%s %s" % ("OK" if ok else "FAIL", detail))
        return 0 if ok else 1
    except Exception as ex:
        import traceback
        if not quiet:
            _msgbox(paths.APP_TITLE, "自检失败：\n%s" % ex, fatal=True)
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
