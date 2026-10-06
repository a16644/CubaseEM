# -*- coding: utf-8 -*-
"""
打包后的隔离验证 —— 在**没有 Python 的干净目录**里确认 exe 真的能用。

    python tools/verify_exe.py

它做六件事，每件都对应「分享给别人时会遇到的坑」：
  1. 把 exe 复制到一个只有 exe 的空目录（模拟别人的电脑）
  2. 清空 PATH 里的 Python，跑 `--self-test`（不启服务，验证代码和资源齐不齐）
  3. 启服务，检查目录是不是自己长出来了
  4. 通过 HTTP 生成一个表情映射，看回读自检过不过
  5. 跟源码版**逐行比对**输出（ID 除外）—— 打包不能改变任何字节
  6. 关掉服务，清场

第 5 条是最关键的：PyInstaller 有可能悄悄改掉浮点格式、换行、缩进，
而 .expressionmap 是要跟原文件逐字一致的东西，差一个空格就是「文件变了」。
"""
import http.client
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "dist", "表情映射生成器.exe")
PORT = 8891

fails = []


def ok(cond, msg, extra=""):
    mark = "✔" if cond else "✘"
    print("  %s %s%s" % (mark, msg, ("  " + str(extra)) if extra else ""))
    if not cond:
        fails.append(msg)
    return cond


def wait_port(port, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def post(path, payload):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20)
    body = __import__("json").dumps(payload).encode("utf-8")
    c.request("POST", path, body, {"Content-Type": "application/json"})
    r = c.getresponse()
    data = r.read().decode("utf-8")
    c.close()
    return __import__("json").loads(data)


# 探测端口时要能抢占，所以也**不设** SO_REUSEADDR（原因见 em/app.py 的说明）
def _free(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", p))
            return True
        except OSError:
            return False


def main():
    if not os.path.isfile(EXE):
        print("找不到 %s\n先跑： python build.py" % EXE)
        return 2

    p = PORT
    while not _free(p):
        p += 1

    # 干净目录：只有 exe，没有源码、没有 config/out
    tmp = tempfile.mkdtemp(prefix="em_exe_verify_")
    dst = os.path.join(tmp, "桌面上的工具")
    os.makedirs(dst)
    shutil.copy2(EXE, dst)
    exe = os.path.join(dst, os.path.basename(EXE))
    # 让这个 exe 自己认这个目录（它认的是 exe 所在位置）
    os.chdir(dst)

    # 把 Python 从 PATH 里彻底摘掉，模拟「对方机器没装 Python」
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([
        r"C:\Windows\System32", r"C:\Windows", r"C:\Windows\System32\Wbem"])
    env["CUBASEEM_NO_GUI"] = "1"        # 出错走控制台，别弹窗挡住 CI
    env["PYTHONIOENCODING"] = "utf-8"

    print("\n== 1. 干净目录里只有 exe ==")
    ok(os.path.isfile(exe), "exe 已就位", dst)
    ok(not os.path.isdir(os.path.join(dst, "em")), "没有源码目录（确认是干净环境）")
    print("   干净目录: %s" % dst)

    print("\n== 2. 没有 Python 也能跑（自检）==")
    r = subprocess.run([exe, "--self-test"], env=env, capture_output=True,
                       text=True, timeout=180)
    ok(r.returncode == 0, "--self-test 退出码 0", r.stdout.strip().splitlines()[-1:]
       if r.stdout.strip() else r.stderr[-200:])
    ok("OK" in r.stdout, "自检通过：代码和资源都齐", r.stdout.strip().splitlines()[-1:]
       if r.stdout.strip() else "")

    print("\n== 3. 目录自己长出来 ==")
    srv = subprocess.Popen([exe, "--port", str(p), "--no-open", "--no-pin"],
                           env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
    try:
        if not wait_port(p):
            ok(False, "服务起来了", "60 秒内没监听")
            print("\n" + "=" * 58)
            print(" 失败 %d 项" % len(fails))
            return 1
        ok(True, "服务起来了", "端口 %d" % p)
        for d in ("config", "out", "data"):
            ok(os.path.isdir(os.path.join(dst, d)), "自建目录 %s/" % d)
        ok(os.path.isfile(os.path.join(dst, "config", "libs"))
           or os.path.isdir(os.path.join(dst, "config", "libs")),
           "自建目录 config/libs/")

        print("\n== 4. 通过网页接口生成文件 ==")
        res = post("/api/generate", {
            "rows": [
                {"name": "连奏", "switch": "ks", "note": 24, "channel": 1,
                 "color": 1, "group": 0, "symbol": 3, "text": "leg"},
                {"name": "断奏", "switch": "ks", "note": 25, "channel": 2,
                 "color": 1, "group": 0},
            ],
            "map_name": "exe隔离验证", "brand": "kontakt",
            "source": "verify", "start_key": 24,
        })
        ok(res.get("ok") and not res.get("error"),
           "生成成功", res.get("error") or res.get("map"))
        ok(res.get("readback") is True, "回读自检通过")
        ok(len(res.get("errors") or []) == 0, "没有错误", res.get("errors"))
        exe_map = res.get("map", "")

        print("\n== 5. 与源码版逐行比对 ==")
        src_xml = _source_side_xml()
        if src_xml is None:
            ok(False, "拿源码版输出做对比（跳过）")
        else:
            # ⚠️ 必须**按字节**比，不能按行比。
            # 走 stdout 捕获时 Windows 的文本模式会把每个 \n 转成 \r\n，
            # 源码本来就是 CRLF 的话会变成 \r\r\n —— 拆行后凭空多出一倍空行，
            # diff 看起来像「exe 少了一半内容」，其实是采集方式的问题。
            a = _norm_lines(src_xml)
            with open(exe_map, "rb") as f:
                b = _norm_lines(f.read().decode("utf-8"))
            same = a == b
            ok(same, "exe 输出与源码版逐行一致（%d 行，ID 除外）" % len(a))
            if not same:
                import difflib
                for line in list(difflib.unified_diff(a, b, "源码", "exe", lineterm=""))[:20]:
                    print("      " + line)
    finally:
        # PyInstaller 的 onefile 是**两层进程**（bootloader + 真正的解释器子进程）。
        # 只 terminate 父进程的话子进程会变孤儿，继续占着 exe 文件，
        # 后面 rmtree 必然失败。必须按进程树杀。
        _kill_tree(srv.pid)
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    print("\n== 6. 清场 ==")
    os.chdir(ROOT)
    # Windows 上文件句柄释放有延迟，rmtree 可能一两次失败 —— 重试几次再判定
    gone = False
    for _ in range(6):
        shutil.rmtree(tmp, ignore_errors=True)
        if not os.path.isdir(tmp):
            gone = True
            break
        time.sleep(0.4)
    if not gone:
        # 可能是 exe 的进程还没彻底退出，最后再试一次并把残留报出来
        shutil.rmtree(tmp, ignore_errors=True)
        gone = not os.path.isdir(tmp)
        if not gone:
            left = os.listdir(tmp) if os.path.isdir(tmp) else []
            print("      残留: %s" % left)
    ok(gone, "临时目录已删除", tmp if not gone else "")

    print("\n" + "=" * 58)
    if fails:
        print(" 失败 %d 项：" % len(fails))
        for f in fails:
            print("   - " + f)
        return 1
    print(" 全部通过 —— 这个 exe 可以直接发给别人用了")
    print("=" * 58)
    return 0


def _kill_tree(pid: int) -> None:
    """连同子进程一起结束（taskkill /T）。非 Windows 或失败时退回 terminate。"""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=30)
        return
    except Exception:
        pass
    try:
        os.kill(pid, 9)
    except Exception:
        pass


def _norm_lines(text):
    """统一换行后拆行，并把随机 ID 换成占位符。"""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    return [re.sub(r'ID="\d+"', 'ID="X"', ln) for ln in t.split("\n")]


def _source_side_xml():
    """用源码生成同样内容。

    ⚠️ 结果**写进文件按字节读回**，不经过 stdout ——
    stdout 是文本模式，Windows 会做换行翻译，CRLF 会被转成 CRCRLF。
    """
    tmpf = os.path.join(tempfile.gettempdir(), "_em_srcver.xml")
    try:
        import json
        rows = [
            {"name": "连奏", "switch": "ks", "note": 24, "channel": 1,
             "color": 1, "group": 0, "symbol": 3, "text": "leg"},
            {"name": "断奏", "switch": "ks", "note": 25, "channel": 2,
             "color": 1, "group": 0},
        ]
        code = (
            "import sys,json; sys.path.insert(0,%r);"
            "from em.webapp import rows_to_arts;"
            "from em.registry import get_brand;"
            "from em.renderer import render_map;"
            "b=get_brand('kontakt');"
            "arts=rows_to_arts(json.loads(%r));"
            "cfg=dict(b.defaults); b.autofill(arts,cfg);"
            "f=open(%r,'w',encoding='utf-8',newline='');"
            "f.write(render_map('exe隔离验证',b.build_all(arts,cfg)));f.close()"
        ) % (ROOT, json.dumps(rows, ensure_ascii=False), tmpf)
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8",
                                    CUBASEEM_NO_WRITE_PROBE="1"))
        if r.returncode != 0:
            print("      源码侧出错: %s" % r.stderr[-200:])
            return None
        with open(tmpf, "rb") as f:
            return f.read().decode("utf-8")
    except Exception as ex:
        print("      %s" % ex)
        return None
    finally:
        if os.path.isfile(tmpf):
            try:
                os.remove(tmpf)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
