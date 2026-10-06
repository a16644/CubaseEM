# -*- coding: utf-8 -*-
"""
一键打包：把整个工具压成一个 **exe**，拷给谁都能双击用，机器上不需要装 Python。

    python build.py            # 打包（默认单文件）
    python build.py --onedir   # 打包成文件夹版（启动快一点，体积小一点）
    python build.py --clean    # 先清掉上次的 build/ dist/ 再打

打包完长这样：
    dist\\表情映射生成器.exe        ← 发给别人就发这个（或整个 dist 文件夹）

**源码一个字都不会动。** 打包只读不写，`em/ config/ tools/` 全部原地保留，
所以改完 bug 重新跑一次 `python build.py` 就能出新版本。
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "表情映射生成器"
ENTRY = os.path.join("em", "app.py")

# 打包时要带上的「非代码」资源 —— 漏了任何一样，exe 起来就会找不到文件
DATA = [
    ("em/web/index.html", "em/web"),          # 网页界面（整个工具就靠它）
]
# 首次运行时希望存在的空目录（config/ 里的 json 是运行时自建的，不带）
DIRS = ["templates"]

# 动态发现的品牌模块：打包后磁盘上扫不到 .py，得把名字写死进环境变量
def _brand_names():
    d = os.path.join(HERE, "em", "methods")
    if not os.path.isdir(d):
        return []
    return [f[:-3] for f in os.listdir(d)
            if f.endswith(".py") and f not in ("__init__.py", "base.py")]


def venv_py() -> str:
    """优先用带 PyInstaller 的那个解释器。"""
    cands = [
        os.path.join(os.path.dirname(sys.executable), "Scripts", "python.exe"),
        sys.executable,
    ]
    for c in cands:
        if os.path.isfile(c) and _has_pyinstaller(c):
            return c
    return ""


def _has_pyinstaller(py: str) -> bool:
    try:
        r = subprocess.run([py, "-c", "import PyInstaller;print(PyInstaller.__version__)"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def main() -> int:
    onedir = "--onedir" in sys.argv
    do_clean = "--clean" in sys.argv

    py = venv_py()
    if not py:
        print("=" * 62)
        print(" 没找到带 PyInstaller 的 Python。装一次就好：")
        print("     python -m pip install pyinstaller")
        print("=" * 62)
        return 2

    if do_clean:
        for d in ("build", "dist"):
            p = os.path.join(HERE, d)
            if os.path.isdir(p):
                print("清掉 %s\\" % d)
                shutil.rmtree(p, ignore_errors=True)

    args = [
        py, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        "--onefile" if not onedir else "--onedir",
        "--windowed",              # 不弹黑窗口，双击像个正常软件
        "--noupx",
    ]

    for src, dst in DATA:
        s = os.path.join(HERE, src)
        if not os.path.isfile(s):
            print("!! 缺资源 %s —— 界面文件丢了，打出来的 exe 打不开" % src)
            return 3
        args += ["--add-data", "%s%s%s" % (s, os.pathsep, dst)]

    for d in DIRS:
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            args += ["--add-data", "%s%s%s" % (p, os.pathsep, d)]

    args += ["--paths", HERE]
    args += ["--hidden-import", "em.app", "--hidden-import", "em.webapp"]

    brands = _brand_names()
    if brands:
        for b in brands:
            args += ["--hidden-import", "em.methods." + b]

    args.append(os.path.join(HERE, ENTRY))

    env = dict(os.environ)
    # 告诉 registry 打包后有哪些品牌模块（源码扫描在 exe 里失效）
    env["CUBASEEM_BRANDS"] = " ".join(brands)
    env["PYTHONIOENCODING"] = "utf-8"

    print("=" * 62)
    print(" 打包 %s" % APP_NAME)
    print(" 解释器: %s" % py)
    print(" 品牌模块: %s" % (", ".join(brands) or "（无）"))
    print("=" * 62)

    r = subprocess.run(args, cwd=HERE, env=env)
    if r.returncode != 0:
        print("\n打包失败。常见原因：")
        print("  · 杀毒软件拦了 build/ dist/ 里的临时 exe —— 关掉再试")
        print("  · 磁盘空间不足")
        print("  · 路径里有特殊字符 —— 试试把项目挪到纯英文路径下")
        return r.returncode

    exe = os.path.join(HERE, "dist", APP_NAME + (".exe" if not onedir else ""))
    if not os.path.isfile(exe):
        print("打包结束但没找到产物：%s" % exe)
        return 4

    mb = os.path.getsize(exe) / 1024.0 / 1024.0
    print("=" * 62)
    print(" 成功: %s" % exe)
    print(" 大小: %.1f MB" % mb)
    print()
    print(" 源码原封不动还在 %s 下，改完 bug 再跑一次 python build.py 就行。" % HERE)
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
