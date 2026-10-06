# -*- coding: utf-8 -*-
"""
本地网页服务端（Python 标准库，不装任何第三方包）。

  python em/webapp.py [--port 8777] [--no-pin]

数据全部落在 config/ 与 out/，只读用户的音源目录，绝不回写。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from em.library import Lib, Item, GLOBAL                 # noqa: E402
from em.presets import Presets                           # noqa: E402
from em.registry import get_brand, list_brands           # noqa: E402
from em.validator import validate                        # noqa: E402
from em.renderer import render_map                       # noqa: E402
from em.reader import read_map                           # noqa: E402
from em.report import write_csv, write_html              # noqa: E402
from em.model import (Art, Cond, parse_group, group_label,     # noqa: E402
                      normalize_symbol, normalize_display_mode,  # noqa: E402
                      default_slot_name, dedupe_art_names, make_unique_names,
                      KS, KS2, CH, KS_CH, CC_MODE, NONE,       # noqa: E402
                      ART_TYPE_LABEL, ART_TYPE_HINT,
                      COND_SEP, COND_KV, COND_EXTRA, encode_conditions,
                      suggest_series,
                      set_octave_offset as _set_octave_offset,
                      get_octave_offset as _get_octave_offset)
from em.parsers import parse_text_file                   # noqa: E402
from em import wintop, palette, paths, locator           # noqa: E402

# ---- 路径统一由 em.paths 提供：源码跑和打包成 exe 都能自动认对位置 ----
paths.ensure_dirs()
ROOT = paths.ROOT
OUT_DIR = paths.OUT_DIR
WEB_DIR = paths.web_dir()
TMP_DIR = paths.D["upload"]


def _apply_octave(v) -> int:
    """设置音名标准（八度基准）。0 = Cubase 默认（24=C0），-1 = 科学记法（24=C1）。"""
    try:
        n = int(v or 0)
    except (TypeError, ValueError):
        n = 0
    n = max(-2, min(2, n))
    _set_octave_offset(n)
    return n


def _default_src() -> str:
    """默认的「收集技法」目录。

    原来写死成 `E:\\Cubase project\\模板文件\\技法` —— 那是**我这台机器**的路径，
    拷给别人必然指向一个不存在的目录。现在改成：
      1. 用户在设置里存过就用存的
      2. 否则自动探测 Cubase 自己的 Expression Maps 目录
      3. 都没有就空着（界面上就显示「未找到」，不报错）
    """
    try:
        saved = (self_saved_src() or "").strip()
    except Exception:
        saved = ""
    if saved and os.path.isdir(saved):
        return saved
    for p in locator.existing():
        return p
    return ""


def self_saved_src() -> str:
    return (Lib(paths.ROOT).settings() or {}).get("default_src", "")


UNSAFE = re.compile(r'[\\/:*?"<>|]')

# 界面缩放：范围与默认值（存进 settings.json）
ZOOM_MIN, ZOOM_MAX, ZOOM_DEFAULT = 80, 150, 100
# 默认技法名：新建行时预填。**默认留空** —— 留空的行会自动叫「插槽N」，
# 比给所有人塞一个「例如 Legato」强得多（那样每行都会重名）。
DEFAULT_NAME = ""


def safe_name(s: str) -> str:
    return UNSAFE.sub("_", (s or "").strip()) or "ExpressionMap"


def resolve_out_dir(raw: str = "") -> str:
    """输出目录：留空 = 默认的 out/。相对路径按程序所在目录解析，不限制到程序内 ——
    用户可能想直接导出到 Cubase 的表情映射目录，那正是这个功能的用处。"""
    d = (raw or "").strip()
    if not d:
        return paths.OUT_DIR
    d = os.path.expandvars(os.path.expanduser(d))
    if not os.path.isabs(d):
        d = os.path.join(paths.ROOT, d)
    return os.path.abspath(d)


def get_setting(lib, key, default=None):
    """从 settings.json 里取一项，取不到给默认值。"""
    try:
        return lib.settings().get(key, default)
    except Exception:
        return default


def zoom_of(cfg: dict) -> int:
    """界面缩放百分比，夹在 80~150 之间。不同屏幕/DPI 都能调。"""
    try:
        z = int(cfg.get("zoom") or ZOOM_DEFAULT)
    except (TypeError, ValueError):
        z = ZOOM_DEFAULT
    return max(ZOOM_MIN, min(ZOOM_MAX, z))


# 表格列宽：10 个整数（勾选 / # / 技法名 / 类型 / 条件层 / 触发方式 / 触发器 /
# 显示色 / 组合 / 操作），存成逗号串，跟缩放一样记在 settings.json 里。
# 前端拖表头右边缘就会发过来；这里做一次清洗，坏值一律丢掉（前端会退回默认）。
COLW_COUNT = 10
COLW_MIN, COLW_MAX = 20, 900


def norm_colw(v) -> str:
    """把列宽清洗成 'w1,w2,...'；给不出 10 个合法值就返回空串（= 用默认）。"""
    if isinstance(v, (list, tuple)):
        parts = list(v)
    elif isinstance(v, str):
        parts = v.split(",")
    else:
        return ""
    if len(parts) != COLW_COUNT:
        return ""
    out = []
    for x in parts:
        try:
            out.append(max(COLW_MIN, min(COLW_MAX, int(str(x).strip()))))
        except (TypeError, ValueError):
            return ""
    return ",".join(str(x) for x in out)


def ensure_dir(path: str) -> str:
    d = resolve_out_dir(path)
    os.makedirs(d, exist_ok=True)
    return d


def brand_options() -> list:
    """给下拉框用：[{id, display}]。只有一个品牌时界面会把它收进「更多设置」。"""
    out = []
    for bid in sorted(list_brands()):
        try:
            disp = get_brand(bid).display
        except Exception:
            disp = bid
        out.append({"id": bid, "display": disp if disp == bid else "%s（%s）" % (disp, bid)})
    return out


def _stash(fname: str, text: str) -> str:
    """网页选上来的文件落到临时目录，再交给现有解析器（不重复造轮子）。"""
    os.makedirs(TMP_DIR, exist_ok=True)
    safe = UNSAFE.sub("_", os.path.basename(fname or "map")) or "map"
    if not safe.lower().endswith(".expressionmap"):
        safe += ".expressionmap"
    path = os.path.join(TMP_DIR, safe)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text or "")
    return path


def art_type_of(v, default: int = 1) -> int:
    """发音法「类型」：属性=0 / 奏法指示=1。认中英文写法，认不出来用默认值。"""
    if v is None or v == "":
        return default
    if isinstance(v, int):
        return 0 if v == 0 else 1
    s = str(v).strip().lower()
    if s in ("0", "attr", "attribute", "属性"):
        return 0
    if s in ("1", "play", "playing", "direction", "奏法", "奏法指示", "指示"):
        return 1
    return default


# ---------------------------------------------------------------- 行 -> Art
def row_to_art(row: dict, index: int) -> Art:
    """界面的一行 -> 中间层 Art。组合行与普通行走不同分支。"""
    sw = (row.get("switch") or "ks").strip()
    atype = art_type_of(row.get("articulationtype"))
    conds = []
    for c in row.get("conditions") or []:
        conds.append(Cond(group=int(c.get("group", 0) or 0),
                          description=str(c.get("description", "") or ""),
                          note=c.get("note"),
                          symbol=normalize_symbol(c.get("symbol")),
                          text=str(c.get("text", "") or ""),
                          displaytype=c.get("displaytype"),
                          display_mode=normalize_display_mode(c.get("display")),
                          articulationtype=art_type_of(c.get("articulationtype"), atype)))
    notes = [int(n) for n in (row.get("notes") or []) if n is not None and n != ""]

    if row.get("combo") and len(conds) > 1:
        # 组合槽位：输出 = 各条件音符合集（notes 可人工覆盖）
        if not notes:
            notes = [c.note for c in conds if c.note is not None]
        if len(notes) >= 2:
            sw = "ks2"
        return Art(
            name=(row.get("name") or "").strip() or default_slot_name(index),
            switch=sw,
            note=notes[0] if notes else None,
            note2=notes[1] if len(notes) > 1 else None,
            color=int(row.get("color") or 1),
            conditions=conds,
            notes=notes,
            order=index,
        )

    if not conds:
        # 界面上每一行都能单独设「记谱符号 / 短标签」，但普通行本来没有
        # condition 条目 —— 行级的这两个值要在这里带上，否则会被丢掉。
        conds = [Cond(group=int(row.get("group", 0) or 0),
                      description=str(row.get("description") or row.get("name") or ""),
                      symbol=normalize_symbol(row.get("symbol")),
                      text=str(row.get("text", "") or ""),
                      display_mode=normalize_display_mode(row.get("display")),
                      articulationtype=atype)]
    a = Art(
        name=(row.get("name") or "").strip() or default_slot_name(index),
        switch=sw,
        note=row.get("note"),
        note2=row.get("note2"),
        channel=row.get("channel"),
        cc_num=row.get("cc_num"),
        cc_val=row.get("cc_val"),
        color=int(row.get("color") or 1),
        description=(row.get("description") or "").strip() or None,
        conditions=conds,
        order=index,
        length_fact=_f(row.get("length_fact"), 1.0),
        velocity_fact=_f(row.get("velocity_fact"), 1.0),
        transpose=_i(row.get("transpose"), 0),
        min_velocity=_i(row.get("min_velocity"), None),
        max_velocity=_i(row.get("max_velocity"), None),
        min_pitch=_i(row.get("min_pitch"), None),
        max_pitch=_i(row.get("max_pitch"), None),
        remote=_i(row.get("remote"), None),
        symbol=normalize_symbol(row.get("symbol")),
        text=str(row.get("text") or ""),
        display_mode=normalize_display_mode(row.get("display")),
        articulationtype=atype,
    )
    if a.note is None and conds and conds[0].note is not None:
        a.note = conds[0].note
    return a


def _i(v, default):
    """界面来的值可能是 ''/None/字符串，统一转成 int 或默认值。"""
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _f(v, default):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _series_text(row: dict, field: str):
    """把一行里某个序列字段抽成 suggest_series 要的字符串。

    - note / note2：MIDI 号
    - channel：1-based 通道（跟界面一致）
    组合行的 note 不参与（输出是多键拼合），返回空串让它跳过。
    """
    if field == "channel":
        v = row.get("channel")
    else:
        if row.get("combo"):
            return ""
        v = row.get(field)
    if v is None or v == "":
        return ""
    try:
        return str(int(v))
    except (TypeError, ValueError):
        return ""


def rows_to_arts(rows: list, display: str = None) -> list:
    """rows -> Art。display 是界面上那把「显示方式」的总开关；
    某一行自己写了 display 就以那一行为准。"""
    mode = normalize_display_mode(display)
    out = []
    for i, r in enumerate(rows or [], start=1):
        a = row_to_art(r, i)
        if mode is not None and normalize_display_mode(r.get("display")) is None:
            a.display_mode = mode
            for c in a.conditions:
                if c.display_mode is None:
                    c.display_mode = mode
        out.append(a)
    return out


# ---------------------------------------------------------------- 冷启动导入
def collect_conditions(lib: Lib, path: str, stem: str = "") -> dict:
    """把一个 .expressionmap 里的『条件』摊平收进全局库（只读源文件）。"""
    _name, arts = read_map(path)
    cond_map = {}
    for a in arts:
        for c in a.conditions:
            desc = (c.description or "").strip()
            if not desc:
                continue
            rec = cond_map.setdefault((int(c.group), desc),
                                      {"note": c.note, "sw": a.switch})
            # 组合槽里缺键的条件：用同层同名单条件槽位的键位回填
            # （Modo Bass / Shreddage 都靠这一步补全）
            if rec["note"] is None and c.note is not None:
                rec["note"] = c.note
            if rec["note"] is None and len(a.conditions) == 1 and a.note is not None:
                rec["note"] = a.note

    items = []
    for (g, desc), rec in cond_map.items():
        sw = rec["sw"] if rec["sw"] in ("ks", "ch", "cc", "none") else "ks"
        it = Item(name=desc, group=g, switch=sw, note=rec["note"], color=1,
                  description=desc, tags=[stem] if stem else [], source=stem)
        if it.ident:          # 没有键位的条件不入库，免得库里堆残缺条目
            items.append(it)
    return lib.import_items(GLOBAL, items)


def import_source_dir(lib: Lib, src_dir: str) -> dict:
    """把一个目录里所有 .expressionmap 的发音法灌进全局库（只读源文件）。"""
    if not os.path.isdir(src_dir):
        return {"error": "目录不存在: %s" % src_dir}
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".expressionmap"))
    per_file = []
    total = 0
    for fn in files:
        path = os.path.join(src_dir, fn)
        stem = os.path.splitext(fn)[0].strip()
        try:
            res = collect_conditions(lib, path, stem)
        except Exception as ex:
            per_file.append({"file": fn, "error": str(ex)})
            continue
        total += res["added"]
        per_file.append({"file": fn, **res})
    return {"files": len(files), "added": total, "detail": per_file}


# ---------------------------------------------------------------- 请求处理
class Handler(BaseHTTPRequestHandler):
    lib = None          # Lib
    presets = None      # Presets
    server_version = "CubaseEM/1.0"

    def log_message(self, fmt, *args):
        pass  # 安静一点，别把控制台刷爆

    # ---- 工具 ----
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    # ---- 路由 ----
    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            path = os.path.join(WEB_DIR, "index.html")
            if not os.path.isfile(path):
                self._send(404, b"index.html missing", "text/plain")
                return
            with open(path, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return

        if p == "/api/state":
            st = self.lib.stats()
            cfg = self.lib.settings()
            out_dir = resolve_out_dir(cfg.get("out_dir") or "")
            self._json({
                "root": ROOT, "out": out_dir, "out_default": OUT_DIR,
                "out_is_default": out_dir == OUT_DIR,
                "out_exists": os.path.isdir(out_dir),
                "brands": brand_options(),
                "palette": palette.get(),
                "stats": st,
                "settings": cfg,
                "zoom": zoom_of(cfg),
                "zoom_min": ZOOM_MIN, "zoom_max": ZOOM_MAX,
                "default_name": cfg.get("default_name") or DEFAULT_NAME,
                "octave_offset": _get_octave_offset(),
                "art_types": [{"v": k, "n": v, "d": ART_TYPE_HINT[k]}
                              for k, v in sorted(ART_TYPE_LABEL.items())],
                "presets": [x.get("name") for x in self.presets.list()],
                "default_src": _default_src(),
                "pinned": wintop.pinned(),
                "pin": wintop.state(),
                "libs": sorted(st.get("libs", {}).keys()),
            })
            return

        if p == "/api/lib":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            scope = (q.get("scope") or [GLOBAL])[0]
            if scope != GLOBAL and not scope:
                scope = GLOBAL
            items = self.lib.items(scope)
            self._json([dict(it.to_dict(), _id=it.id, _key=it.key_name,
                             _group_label=group_label(it.group))
                        for it in items])
            return

        if p == "/api/search":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            self._json(self.lib.search((q.get("q") or [""])[0],
                                       (q.get("source") or [""])[0]))
            return

        if p == "/api/audit":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            scope = (q.get("scope") or [GLOBAL])[0] or GLOBAL
            self._json(self.lib.audit(scope))
            return

        if p == "/api/presets":
            self._json(self.presets.list())
            return

        if p == "/api/pin_status":
            self._json({"pinned": wintop.pinned(), **wintop.state()})
            return

        if p == "/api/palette":
            self._json(palette.get())
            return

        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        p = urlparse(self.path).path
        b = self._body()

        if p == "/api/check":
            src = b.get("source") or ""
            it = Item.from_row(b.get("row") or {}, source=src)
            conf = self.lib.find_conflict(src or GLOBAL, it)
            same = self.lib.find_same_name(src or GLOBAL, it)
            gconf = self.lib.find_conflict(GLOBAL, it) if src else None
            self._json({
                "id": it.id,
                "conflict": conf.to_dict() if conf else None,
                "global_conflict": gconf.to_dict() if gconf else None,
                "same_name": [x.to_dict() for x in same],
                "free_key": self.lib.free_key(src or GLOBAL, it.group, it.switch)
                if conf or gconf else None,
            })
            return

        if p == "/api/save":
            src = b.get("source") or ""
            scope = b.get("scope") or (src or GLOBAL)
            it = Item.from_row(b.get("row") or {}, source=src)
            status, conf = self.lib.save(scope, it)
            self._json({"status": status,
                        "conflict": conf.to_dict() if conf else None,
                        "id": it.id,
                        "free_key": self.lib.free_key(scope, it.group, it.switch)
                        if status == "conflict" else None})
            return

        if p == "/api/promote":
            src = b.get("source") or ""
            it = Item.from_row(b.get("row") or {}, source=src)
            status, conf = self.lib.promote(it)
            self._json({"status": status,
                        "conflict": conf.to_dict() if conf else None,
                        "free_key": self.lib.free_key(GLOBAL, it.group, it.switch)
                        if status == "conflict" else None})
            return

        if p == "/api/lib/update":
            hit = self.lib.update(b.get("scope") or GLOBAL, b.get("id"), b.get("patch") or {})
            self._json({"ok": hit is not None,
                        "item": hit.to_dict() if hit else None})
            return

        if p == "/api/lib/delete":
            self._json({"ok": self.lib.delete(b.get("scope") or GLOBAL, b.get("id"))})
            return

        if p == "/api/audit":
            self._json(self.lib.audit(b.get("scope") or GLOBAL))
            return

        if p == "/api/rename_spelling":
            n = self.lib.rename_spelling(b.get("scope") or GLOBAL,
                                         b.get("target"), b.get("ids") or [])
            self._json({"changed": n})
            return

        if p == "/api/import":
            src_dir = b.get("dir") or _default_src()
            if not src_dir:
                self._json({"ok": False, "error": "没找到可收集的目录。"
                            "请用「选多个 .expressionmap 文件」手动挑。",
                            "need_pick": True})
                return
            self._json(import_source_dir(self.lib, src_dir))
            return

        if p == "/api/presets/save":
            p2 = self.presets.save(b.get("name") or "未命名模板",
                                   b.get("layers") or [],
                                   b.get("combos") or [],
                                   b.get("prefix") or "插槽")
            self._json({"ok": True, "preset": p2,
                        "names": [x.get("name") for x in self.presets.list()]})
            return

        if p == "/api/presets/delete":
            self._json({"ok": self.presets.delete(b.get("name"))})
            return

        if p == "/api/parse_paste":
            text = b.get("text") or ""
            try:
                arts, warns = parse_text_file_text(text, b.get("default_switch") or "ks")
            except Exception as ex:
                self._json({"error": str(ex)})
                return
            self._json({"rows": arts_to_rows(arts), "warnings": warns})
            return

        if p == "/api/generate":
            self._json(self._generate(b))
            return

        if p == "/api/ping":
            # 心跳：页面每隔几秒打一次。
            # 用来判断「浏览器窗口是不是被关了」——关掉窗口就该让程序跟着退，
            # 否则进程一直挂着、端口一直被占，下次双击就弹「端口被占用」。
            _LAST_PING[0] = time.time()
            self._json({"ok": True, "ts": _LAST_PING[0]})
            return

        if p == "/api/shutdown":
            # 打包成 GUI exe 之后没有控制台，用户没法按 Ctrl+C。
            # 界面上给一个「退出程序」按钮，走这里。
            self._json({"ok": True})
            threading.Thread(target=_shutdown, daemon=True).start()
            return

        if p == "/api/pin":
            # 置顶要把窗口上去之后「回读」系统的样式位再答复，别让界面自己记住状态
            want = bool(b.get("on", True))
            hits = wintop.pin(want)
            st = wintop.state()
            if want and not hits:
                self._json({"ok": False, "error": "没找到编辑器窗口", "pin": st})
                return
            self._json({"ok": st["pinned"] == want, "want": want,
                        "windows": hits, "pin": st})
            return

        if p == "/api/palette/save":
            self._json(palette.save(b.get("palette") or []))
            return

        if p == "/api/load_map":
            # 把一个现成的表情映射「原样打开」到表格里，用于改动后另存
            try:
                path = _stash(b.get("file") or "map.expressionmap", b.get("text") or "")
                map_name, arts = read_map(path)
            except Exception as ex:
                self._json({"error": "读不出来：%s" % ex})
                return
            rows = arts_to_rows(arts)
            for r in rows:
                r["_saved"] = False
            self._json({"map_name": map_name, "rows": rows, "count": len(rows),
                        "combos": sum(1 for r in rows if r.get("combo"))})
            return

        if p == "/api/import_files":
            # 批量把若干表情映射里的发音法收进技法清单（不改动原文件）
            items = b.get("items") or []
            detail, added, upd = [], 0, 0
            for it in items:
                stem = os.path.splitext(os.path.basename(it.get("file") or "map"))[0].strip()
                try:
                    path = _stash(it.get("file") or "map.expressionmap", it.get("text") or "")
                    res = self._collect_conditions(path, stem)
                except Exception as ex:
                    detail.append({"file": it.get("file"), "error": str(ex)})
                    continue
                added += res.get("added", 0)
                upd += res.get("updated", 0)
                detail.append({"file": it.get("file"), **res})
            self._json({"files": len(items), "added": added, "updated": upd,
                        "detail": detail})
            return

        if p == "/api/settings":
            patch = dict(b.get("patch") or {})
            if "zoom" in patch:
                patch["zoom"] = max(ZOOM_MIN, min(ZOOM_MAX, _i(patch["zoom"], ZOOM_DEFAULT)))
            if "out_dir" in patch:
                # 存原样（空字符串 = 用默认），只在生成时解析成绝对路径
                patch["out_dir"] = str(patch["out_dir"] or "").strip()
            if "default_name" in patch:
                patch["default_name"] = str(patch["default_name"] or "").strip()
            if "octave_offset" in patch:
                patch["octave_offset"] = _apply_octave(patch["octave_offset"])
            if "colw" in patch:
                # 表格列宽（前端拖表头改的）。清洗不过就存空串 → 前端用默认列宽
                patch["colw"] = norm_colw(patch["colw"])
            self.lib.set_settings(patch)
            cfg = self.lib.settings()
            out_dir = resolve_out_dir(cfg.get("out_dir") or "")
            self._json({"settings": cfg, "zoom": zoom_of(cfg),
                        "out": out_dir, "out_is_default": out_dir == OUT_DIR})
            return

        if p == "/api/open_folder":
            # 打开导出文件夹（或指定目录）。Windows 下用系统的资源管理器。
            target = b.get("dir") or self.lib.settings().get("out_dir") or ""
            path = resolve_out_dir(target)
            if not os.path.isdir(path):
                try:
                    os.makedirs(path, exist_ok=True)
                except OSError as ex:
                    self._json({"ok": False, "error": "目录建不出来：%s" % ex, "dir": path})
                    return
            opened = ""
            try:
                os.startfile(path)                      # noqa: S606  (Windows 专用)
                opened = "explorer"
            except AttributeError:
                # 非 Windows 兜底
                for cmd in (["xdg-open", path], ["open", path]):
                    try:
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                        opened = cmd[0]
                        break
                    except OSError:
                        continue
            except OSError as ex:
                self._json({"ok": False, "error": "打不开：%s" % ex, "dir": path})
                return
            self._json({"ok": bool(opened), "dir": path, "by": opened})
            return

        if p == "/api/suggest":
            # 键位/通道的「下一个该填什么」——界面上那行暗色提示就是它
            rows = b.get("rows") or []
            field = b.get("field") or "note"
            lo, hi = (0, 127) if field in ("note", "note2") else (1, 16)
            formulas, snaps = [], []
            for r in rows:
                formulas.append(_series_text(r, field))
                snaps.append({"switch": r.get("switch"),
                              "combo": bool(r.get("combo")),
                              "cc_num": r.get("cc_num")})
            res = suggest_series(formulas, snaps, lo=lo, hi=hi)
            self._json(res)
            return

        self._send(404, b"not found", "text/plain")

    def _collect_conditions(self, path: str, stem: str) -> dict:
        return collect_conditions(self.lib, path, stem)

    # ---- 生成 ----
    def _generate(self, b: dict) -> dict:
        # 音名标准（八度基准）是全局的：解析和显示必须同时切，
        # 只切一边就会出现「填 C0 导出成 C-1」这种差八度的怪事。
        if b.get("octave_offset") is not None:
            _apply_octave(b["octave_offset"])
        rows = b.get("rows") or []
        map_name = (b.get("map_name") or "").strip() or "ExpressionMap"
        brand_id = b.get("brand") or "kontakt"
        source = b.get("source") or ""
        if not rows:
            return {"error": "表格是空的"}
        brand = get_brand(brand_id)
        cfg = dict(brand.defaults)
        if b.get("start_key") is not None:
            cfg["keyswitch_base"] = int(b["start_key"])
        arts = rows_to_arts(rows, b.get("display"))
        # 名字去重：空名 -> 「插槽N」，重名加 (2)/(3)。写进 Cubase 的条目靠名字认，
        # 重名的话列表里完全分不出谁是谁，所以这一步在生成前必做。
        renamed = dedupe_art_names(arts)
        # 「自动补触发键」开关（界面上默认**不打开**）：打开才按品牌规则补
        # 触发键 / 第二键 / 通道；不打开就按你填的原样生成 ——
        # 类型写「按键切换」但键位空 + 有通道，出来就是 key=-1 + 通道（纯通道触发）。
        fill = brand.autofill(arts, cfg, fill_triggers=bool(b.get("autofill")))
        errors, warns = validate(arts)
        slots = brand.build_all(arts, cfg)
        xml_text = render_map(map_name, slots)

        # 输出目录：本次请求指定的优先，其次是设置里存的，都没有就 out/
        out_dir = resolve_out_dir(b.get("out_dir")
                                 or self.lib.settings().get("out_dir") or "")
        base = safe_name(b.get("out") or map_name)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as ex:
            return {"error": "输出目录建不出来：%s（%s）" % (out_dir, ex)}

        # 先把要写的四个文件列出来，挨个看有没有同名的。
        # 有同名且用户还没确认过 -> 只回报清单，什么都不写，等界面问过再说。
        targets = [base + ext for ext in (".expressionmap", ".html", ".csv", ".log")]
        existing = [n for n in targets if os.path.exists(os.path.join(out_dir, n))]
        if existing and not b.get("overwrite"):
            return {"need_confirm": True,
                    "existing": existing,
                    "out_dir": out_dir,
                    "base": base,
                    "renamed": renamed}

        f_map = os.path.join(out_dir, base + ".expressionmap")
        try:
            with open(f_map, "w", encoding="utf-8", newline="") as f:
                f.write(xml_text)
            notes = list(fill) + ["[警告] " + w for w in warns]
            f_html = write_html(os.path.join(out_dir, base + ".html"), map_name, arts, brand_id, notes)
            f_csv = write_csv(os.path.join(out_dir, base + ".csv"), map_name, arts)
            f_log = os.path.join(out_dir, base + ".log")
            with open(f_log, "w", encoding="utf-8", newline="") as f:
                f.write("映射名: %s\n音源: %s\n品牌: %s\n技法数: %d\n\n" %
                        (map_name, source, brand_id, len(arts)))
                f.write("[自动补全]\n" + ("\n".join(fill) or "（无）") + "\n\n")
                f.write("[错误]\n" + ("\n".join(errors) or "（无）") + "\n\n")
                f.write("[警告]\n" + ("\n".join(warns) or "（无）") + "\n")
        except OSError as ex:
            return {"error": "写不进去：%s（%s）" % (f_map, ex)}

        ok = False
        try:
            back_name, back_arts = read_map(f_map)
            ok = back_name == map_name and len(back_arts) == len(arts)
        except Exception:
            pass
        return {"ok": True, "map": f_map, "html": f_html, "csv": f_csv, "log": f_log,
                "count": len(arts), "errors": errors, "warnings": list(fill) + list(warns),
                "readback": ok, "out_dir": out_dir, "renamed": renamed}


def parse_text_file_text(text: str, default_switch: str):
    """复制文本 -> Art（写临时文件复用现有解析器，避免重复造轮子）。"""
    tmp = os.path.join(OUT_DIR, "_paste_tmp.txt")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    return parse_text_file(tmp, default_switch)


def arts_to_rows(arts: list) -> list:
    out = []
    for a in arts:
        conds = [c.to_dict() for c in a.conditions]
        if len(conds) == 1 and conds[0].get("note") is None and a.note is not None:
            conds[0]["note"] = a.note   # 单条件行的键位要落到条件上，组合时才拼得出输出
        out.append({
            "name": a.name,
            "group": int(a.conditions[0].group) if a.conditions else 0,
            "switch": a.switch,
            "note": a.note, "note2": a.note2, "channel": a.channel,
            "cc_num": a.cc_num, "cc_val": a.cc_val,
            "color": a.color or 1,
            "description": a.description or "",
            "combo": len(a.conditions) > 1,
            "conditions": conds,
            "notes": a.out_notes(),
            # 高级参数（收在「更多参数」里，平时不占地方）
            "length_fact": a.length_fact,
            "velocity_fact": a.velocity_fact,
            "transpose": a.transpose,
            "min_velocity": a.min_velocity,
            "max_velocity": a.max_velocity,
            "min_pitch": a.min_pitch,
            "max_pitch": a.max_pitch,
            "remote": a.remote,
            "symbol": a.symbol if a.symbol is None else a.symbol,
            "text": a.text or "",
            "display": a.display_mode or "",
            # 发音法类型：属性 0 / 奏法指示 1
            "articulationtype": (a.articulationtype
                                 if a.articulationtype is not None else 1),
            "has_visual": a.has_visual,
        })
    return out


# ---------------------------------------------------------------- 启动
_SERVERS = []

# 心跳：最近一次页面 ping 的时间戳。页面被关掉后就再没有心跳进来。
_LAST_PING = [0.0]
# 只有在「允许自动退出」时看门狗才干活（命令行/python 跑时不该自己退）
_AUTO_EXIT = [False]


def _kill_parent_tree() -> None:
    """把 onefile 的父进程（bootloader）一起带走。

    PyInstaller 单文件模式运行时其实是**两个**进程：外层启动器 + 内层 Python。
    只退内层的话外层会挂着，用户看到的就是「关了窗口但进程还在、端口还被占」。
    非冻结时**绝对不能动父进程**——那可能是用户的命令行或 IDE。
    """
    if not getattr(sys, "frozen", False):
        return
    ppid = os.getppid()
    if ppid <= 1 or ppid == os.getpid():
        return
    try:
        subprocess.run(["taskkill", "/PID", str(ppid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def _shutdown() -> None:
    """真正停掉服务并让进程退出。

    GUI 模式下没有控制台，只能由界面主动调起（或页面关掉时的心跳看门狗）。
    要先回完 HTTP 响应再退，所以调用方已经另起线程并先 `_json` 过了。
    """
    import time as _t
    _t.sleep(0.4)                       # 等响应发出去
    for s in _SERVERS:
        try:
            s.shutdown()
        except Exception:
            pass
    _kill_parent_tree()
    # os._exit 是唯一能可靠退掉 GUI 进程的办法：后台还有守护线程、非 daemon 线程
    # 的话，正常的 sys.exit 会卡住等它们结束。
    os._exit(0)


# 心跳间隔（秒）—— 必须比看门狗超时小得多，否则「超时判死」会误杀正常服务。
# index.html 里的 setInterval 要跟这个数对上。
BEAT_SECONDS = 8.0


def start_watchdog(seconds: float = 0.0) -> None:
    """`seconds` 给 0 就取环境变量 CUBASEEM_AUTOCLOSE（默认 180 秒）。"""
    """页面长时间没有心跳就自动退出——等价于「关掉窗口 = 程序退出」。

    为什么需要它：双击 exe 打开的是浏览器窗口，窗口右上角的 × 关闭的是浏览器，
    服务进程收不到任何通知。不主动退，端口就被一直占着，下次双击就报错。

    窗口后台化时浏览器会把定时器节流到 1 分钟一次，所以超时取 120 秒留余量，
    并且页面从后台切回来时会立刻补一发心跳（见 index.html 的 keepalive）。
    """
    if not seconds:
        try:
            seconds = float(os.environ.get("CUBASEEM_AUTOCLOSE") or 0)
        except ValueError:
            seconds = 0.0
    if not seconds:
        seconds = 180.0
    # ⚠️ 超时必须远大于心跳间隔，否则服务会被自己误判成「页面没了」而退出。
    #    切到后台的标签页会被浏览器节流到 1 分钟一次，这里留足余量。
    seconds = max(seconds, BEAT_SECONDS * 3)

    def run():
        while True:
            time.sleep(1.0)
            # 只有「允许自动退出」（exe 双击启动）时才看这个门
            if not _AUTO_EXIT[0]:
                continue
            # ⚠️ 从没 ping 过 = 没有页面在跑（比如用户自己输地址打开的），
            #    这时候**绝对不能**自作主张退出 —— 那是人还在用的服务。
            last = _LAST_PING[0]
            if not last:
                continue
            if (time.time() - last) < seconds:
                continue
            _shutdown()

    threading.Thread(target=run, daemon=True).start()


_STARTED_AT = [time.time()]


def _launch_browser(url: str):
    """优先用 Edge / Chrome 的 --app 模式（无地址栏，标题干净，好置顶）。"""
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for exe in cands:
        if os.path.isfile(exe):
            try:
                subprocess.Popen([exe, "--app=" + url, "--new-window",
                                  "--window-size=1360,900"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return exe
            except OSError:
                continue
    webbrowser.open(url)
    return "default"


def _pin_when_ready(url: str, tries: int = 40):
    """浏览器窗口出现后再置顶（最多等 20 秒）。"""

    def run():
        for _ in range(tries):
            if wintop.find_windows():
                wintop.pin(True)
                return
            time.sleep(0.5)

    threading.Thread(target=run, daemon=True).start()


def start(port: int = 8777, open_browser: bool = True, pin: bool = True,
          auto_exit: bool = False, close_timeout: float = 0.0):
    """起服务。

    `auto_exit=True` 时开「关掉浏览器窗口 = 程序退出」的看门狗（双击 exe 的场景）。
    ⚠️ 浏览器**只能开一次**：调用方（em/app.py）负责开，这里就别再开了，
    否则双击 exe 会弹出两个一模一样的窗口。
    """
    _AUTO_EXIT[0] = bool(auto_exit)
    Handler.lib = Lib(ROOT)
    Handler.presets = Presets(ROOT)
    # 存过的音名标准要先恢复，否则界面显示的八度号和设置对不上
    _apply_octave(Handler.lib.settings().get("octave_offset"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    _SERVERS.append(srv)                 # 供 /api/shutdown 关掉
    url = "http://127.0.0.1:%d/" % port
    # ⚠️ 打包成 exe 时是 --windowed，没有控制台 → sys.stdout 是 None。
    #    这里**只能**用 paths._say，绝对不能 print —— print 会抛
    #    AttributeError，服务线程直接死掉，界面就永远打不开了。
    for line in ("=" * 60,
                 "  Cubase 表情映射编辑器",
                 "  地址: %s" % url,
                 "  项目: %s" % ROOT,
                 "  停止: 关掉浏览器窗口，程序自动退出",
                 "=" * 60):
        paths._say(line)
    if auto_exit:
        start_watchdog(close_timeout)
    if open_browser:
        _launch_browser(url)
        if pin:
            _pin_when_ready(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        paths._say("\n已停止。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Cubase 表情映射网页编辑器")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-open", action="store_true", help="不自动开浏览器")
    ap.add_argument("--no-pin", action="store_true", help="不自动置顶")
    a = ap.parse_args()
    return start(a.port, not a.no_open, not a.no_pin)


if __name__ == "__main__":
    sys.exit(main())
