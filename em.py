# -*- coding: utf-8 -*-
"""
Cubase 12 表情映射自动生成工具 —— 总控 CLI。

  em.py build --in data/x.csv  --brand kontakt --out "音色库名"
  em.py build --paste data/t.txt --brand kontakt --out "音色库名"
  em.py dump  --map out/x.expressionmap            # 反向导出 CSV
  em.py dump  --dir  "E:\\..." --csv-dir out/csv   # 批量反向导出
  em.py doctor
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台下强制 UTF-8 输出（配合 bat 里的 chcp 65001）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from em import locator                      # noqa: E402
from em.parsers import parse_csv, map_name_from_csv, parse_text_file, set_octave_offset  # noqa: E402
from em.registry import get_brand, list_brands    # noqa: E402
from em.validator import validate                 # noqa: E402
from em.renderer import render_map                # noqa: E402
from em.reader import read_map                    # noqa: E402
from em.report import write_csv, write_html       # noqa: E402
from em.model import dedupe_art_names             # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "out")
UNSAFE = re.compile(r'[\\/:*?"<>|]')


def safe_name(s: str) -> str:
    s = UNSAFE.sub("_", (s or "").strip())
    return s or "ExpressionMap"


def cmd_build(args):
    # 1. 解析输入（八度校准必须在解析前设置）
    if args.octave_offset:
        set_octave_offset(args.octave_offset)

    if args.paste:
        arts, warns = parse_text_file(args.paste, args.default_switch)
        src = args.paste
    else:
        if not args.inp:
            print("错误: 需要 --in <csv> 或 --paste <txt>", file=sys.stderr)
            return 2
        arts = parse_csv(args.inp)
        warns = []
        src = args.inp

    # 1.5 显示方式（CLI 全局覆盖；CSV 里逐行写了 display 列的就以 CSV 为准）
    from em.model import normalize_display_mode
    global_mode = normalize_display_mode(getattr(args, "display", None) or None)
    if global_mode:
        for a in arts:
            if a.display_mode is None:
                a.display_mode = global_mode
            for c in a.conditions:
                if c.display_mode is None:
                    c.display_mode = global_mode
        if global_mode == "text":
            print("  显示方式: 文本（使用者在 Cubase 发音法里看到技法名）")

    if not arts:
        print("错误: 没有解析出任何技法", file=sys.stderr)
        return 2

    # 1.6 名字去重：空名 -> 「插槽N」，重名加 (2)/(3)。
    # Cubase 里认条目全靠名字，重名等于两条长得一模一样，必须避免。
    renamed = dedupe_art_names(arts)
    if renamed:
        print("  名字去重: %d 个（%s）" %
              (len(renamed), "、".join(renamed[:6]) + ("…" if len(renamed) > 6 else "")))

    # 2. 品牌模块：规则层自动补全
    brand = get_brand(args.brand)
    cfg = dict(brand.defaults)
    if args.keyswitch_base is not None:
        cfg["keyswitch_base"] = args.keyswitch_base
    if args.start_channel is not None:
        cfg["start_channel"] = args.start_channel
    fill_log = brand.autofill(arts, cfg, fill_triggers=not args.no_autofill)

    # 3. 校验
    errors, vwarns = validate(arts)
    notes = list(warns) + list(fill_log)
    if errors:
        print("\n[校验] 发现 %d 个错误:" % len(errors))
        for e in errors:
            print("  ✗ " + e)
        if not args.force:
            print("\n已中止。修好后再跑，或加 --force 强行生成。")
            return 1
        notes.append("已用 --force 强行生成，存在 %d 个错误" % len(errors))
    if vwarns:
        notes.extend("[警告] " + w for w in vwarns)
        print("\n[校验] %d 条警告:" % len(vwarns))
        for w in vwarns[:10]:
            print("  ! " + w)
        if len(vwarns) > 10:
            print("  ... 其余 %d 条见日志" % (len(vwarns) - 10))

    # 4. 渲染
    # 取名优先级：--name > CSV 里的 map_name 列 > --out > 源文件名
    csv_name = map_name_from_csv(args.inp) if (args.inp and not args.paste) else ""
    src_stem = os.path.splitext(os.path.basename(src))[0] if src else ""
    map_name = (args.name or csv_name or args.out or safe_name(src_stem) or "ExpressionMap")
    slots = brand.build_all(arts, cfg)
    xml_text = render_map(map_name, slots)

    # 5. 落盘
    os.makedirs(OUT_DIR, exist_ok=True)
    base = safe_name(args.out or map_name)
    # 同名文件先问一声：写出来的是一套 4 个文件，闷头覆盖会把上一版顶掉。
    exts = (".expressionmap", ".html", ".csv", ".log")
    targets = [os.path.join(OUT_DIR, base + e) for e in exts]
    exist = [p for p in targets if os.path.exists(p)]
    if exist and not getattr(args, "overwrite", False):
        print("\n[同名文件] 输出目录里已经有这些文件：")
        for p in exist:
            print("  · " + p)
        if not sys.stdin or not sys.stdin.isatty():
            print("\n非交互环境，已停下。要覆盖请加 --overwrite。")
            return 1
        try:
            ans = input("覆盖它们吗？(y/N) ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes", "是", "覆盖", "1"):
            print("已取消，没有写任何文件。")
            return 1
    f_map = os.path.join(OUT_DIR, base + ".expressionmap")
    with open(f_map, "w", encoding="utf-8", newline="") as f:
        f.write(xml_text)
    f_html = write_html(os.path.join(OUT_DIR, base + ".html"), map_name,
                        slots and arts, args.brand, notes)
    f_csv = write_csv(os.path.join(OUT_DIR, base + ".csv"), map_name, arts)
    f_log = os.path.join(OUT_DIR, base + ".log")
    with open(f_log, "w", encoding="utf-8") as f:
        f.write("来源: %s\n品牌模块: %s\n映射名: %s\n技法数: %d\n\n" %
                (src, args.brand, map_name, len(arts)))
        f.write("[自动补全]\n" + ("\n".join(fill_log) or "（无）") + "\n\n")
        f.write("[错误]\n" + ("\n".join(errors) or "（无）") + "\n\n")
        f.write("[警告]\n" + ("\n".join(warns + vwarns) or "（无）") + "\n")

    # 6. 回读自检
    try:
        back_name, back_arts = read_map(f_map)
        ok = (back_name == map_name and len(back_arts) == len(arts))
    except Exception as ex:
        ok = False
        print("  ⚠ 回读自检失败: %s" % ex)

    print("\n✔ 生成完成: %s" % f_map)
    print("  映射名   : %s" % map_name)
    print("  技法数   : %d" % len(arts))
    print("  对照表   : %s" % f_html)
    print("  CSV      : %s" % f_csv)
    print("  日志     : %s" % f_log)
    print("  回读自检 : %s" % ("通过" if ok else "未通过"))
    if notes:
        print("  提示     : %d 条（见日志）" % len(notes))
    print("\n放到 Cubase 读取目录即可加载:")
    print("  " + (locator.existing()[0] if locator.existing() else locator.candidates()[0]))
    return 0


def cmd_dump(args):
    targets = []
    if args.map:
        targets.append(args.map)
    elif args.dir:
        for fn in sorted(os.listdir(args.dir)):
            if fn.lower().endswith(".expressionmap"):
                targets.append(os.path.join(args.dir, fn))
    else:
        print("错误: 需要 --map 或 --dir", file=sys.stderr)
        return 2

    out_dir = args.csv_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    for t in targets:
        try:
            name, arts = read_map(t)
        except Exception as ex:
            print("  ✗ 解析失败 %s: %s" % (t, ex))
            continue
        out = os.path.join(out_dir, safe_name(os.path.splitext(os.path.basename(t))[0]) + ".csv")
        write_csv(out, name, arts)
        print("  ✔ %-52s -> %d 条技法" % (os.path.basename(t), len(arts)))
    print("\nCSV 输出目录: %s" % out_dir)
    return 0


def cmd_web(args):
    """启动本地网页编辑器（三栏：技法库 / 编辑表格 / 组合配置）。"""
    from em import webapp
    return webapp.start(args.port, not args.no_open, not args.no_pin)


def cmd_doctor(args):
    print("Python  :", sys.version.split()[0])
    print("项目根  :", ROOT)
    print("品牌模块:", ", ".join(sorted(list_brands())))
    print(locator.report())
    return 0


def cmd_menu(args):
    """交互式中文菜单 —— 给不想碰命令行的人用，支持把文件直接拖进窗口。"""
    brands = sorted(list_brands())

    def ask(prompt):
        # Windows 拖放进控制台的路径会带引号
        return input(prompt).strip().strip('"').strip("'")

    print("\n提示：输入路径时可以直接把文件/文件夹拖进这个窗口，会自动填好路径。")
    try:
        while True:
            print("\n" + "=" * 48)
            print("   Cubase 12 表情映射生成工具")
            print("=" * 48)
            print("   1. 从 CSV 生成表情映射")
            print("   2. 从复制的文本生成（音源界面 / 说明书）")
            print("   3. 把现有 .expressionmap 反转成 CSV")
            print("   4. 打开网页编辑器（推荐）")
            print("   5. 环境自检 / 查看输出目录")
            print("   0. 退出")
            c = ask("\n请选择 [0-5]: ")

            if c == "0":
                return 0

            if c in ("1", "2"):
                p = ask("\n文件路径（可直接拖进来）: ")
                if not p:
                    print("  未输入路径，已取消")
                    continue
                if not os.path.exists(p):
                    print("  文件不存在: %s" % p)
                    continue
                brand = brands[0]
                if len(brands) > 1:
                    print("  可用品牌: " + ", ".join(brands))
                    b = ask("  品牌 [默认 %s]: " % brand)
                    if b in brands:
                        brand = b
                name = ask("  映射名（显示在 Cubase 里，回车跳过）: ")
                out = ask("  输出文件名（回车用映射名）: ")
                ns = argparse.Namespace(
                    inp=(p if c == "1" else None),
                    paste=(p if c == "2" else None),
                    brand=brand, out=(out or None), name=(name or None),
                    keyswitch_base=None, start_channel=None, octave_offset=0,
                    default_switch="ks", force=False)
                cmd_build(ns)
                input("\n回车继续...")

            elif c == "3":
                p = ask("\n文件或整个目录的路径（可直接拖进来）: ")
                if not p or not os.path.exists(p):
                    print("  路径无效")
                    continue
                ns = argparse.Namespace(
                    map=(None if os.path.isdir(p) else p),
                    dir=(p if os.path.isdir(p) else None),
                    csv_dir=None)
                cmd_dump(ns)
                input("\n回车继续...")

            elif c == "4":
                print("\n正在打开网页编辑器（窗口会自动置顶）…")
                print("用完回到这个窗口按 Ctrl+C 即可停止服务。\n")
                cmd_web(argparse.Namespace(port=8777, no_open=False, no_pin=False))

            elif c == "5":
                cmd_doctor(argparse.Namespace())
                print("\n输出目录:", OUT_DIR)
                input("\n回车继续...")

            else:
                print("  没有这个选项")
    except EOFError:
        print("\n（输入结束，已退出）")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="em.py", description="Cubase 12 表情映射自动生成")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="生成 .expressionmap")
    b.add_argument("--in", dest="inp", help="输入 CSV")
    b.add_argument("--paste", help="输入复制文本")
    b.add_argument("--brand", default="kontakt")
    b.add_argument("--out", help="输出文件名（不含扩展名）")
    b.add_argument("--name", help="映射名（显示在 Cubase 里）")
    b.add_argument("--keyswitch-base", type=int, help="自动补键起始音符，默认 24")
    b.add_argument("--start-channel", type=int, help="自动补通道起始通道，默认 1")
    b.add_argument("--no-autofill", action="store_true",
                   help="不自动补触发键 / 通道：键位空就空着（生成出来靠通道 / CC 触发）。"
                        "网页界面上对应「更多设置」里的「自动补触发键」开关，那边默认是关的")
    b.add_argument("--octave-offset", type=int, default=0,
                   help="音名标准校准：0 = Cubase 默认（24 叫 C0，中央 C=C3），"
                        "-1 = 科学记法（24 叫 C1，中央 C=C4）")
    b.add_argument("--default-switch", default="ks",
                   help="复制文本中没识别出音符的行按什么处理，默认 ks（自动补键）")
    b.add_argument("--display", dest="display", default=None,
                   choices=["auto", "text", "symbol"],
                   help="发音法里给使用者看的那一段用文本还是符号。"
                        "text=显示技法名（推荐），symbol=用 Cubase 符号编号，"
                        "auto=按每行填的「符号」列自动判断。默认 auto")
    b.add_argument("--force", action="store_true", help="有错也生成")
    b.add_argument("--overwrite", action="store_true",
                   help="输出目录里已有同名文件时直接覆盖，不再询问")
    b.set_defaults(func=cmd_build)

    d = sub.add_parser("dump", help="反向导出 CSV")
    d.add_argument("--map", help="单个 .expressionmap")
    d.add_argument("--dir", help="整个目录批量")
    d.add_argument("--csv-dir", help="CSV 输出目录")
    d.set_defaults(func=cmd_dump)

    w = sub.add_parser("web", help="打开网页编辑器")
    w.add_argument("--port", type=int, default=8777)
    w.add_argument("--no-open", action="store_true")
    w.add_argument("--no-pin", action="store_true", help="不自动置顶")
    w.set_defaults(func=cmd_web)

    doc = sub.add_parser("doctor", help="环境自检")
    doc.set_defaults(func=cmd_doctor)

    m = sub.add_parser("menu", help="交互式菜单（推荐）")
    m.set_defaults(func=cmd_menu)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
