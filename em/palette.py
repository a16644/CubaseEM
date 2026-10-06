# -*- coding: utf-8 -*-
"""
Cubase 表情映射里的「显示色」。

PSoundSlot 的 color 是一个 1~16 的调色板编号（还有 104 = 不指定），
Cubase 里要勾选「音符着色 = 声音插槽」时才会看到 —— 它让每个发音法在钢琴窗里
显示成不同颜色，**完全不影响发声**。

注意：这里的 RGB 是「贴近 Cubase 观感的近似色」。真机的色板以 Cubase 为准；
如果发现某号色对不上，改 `config/palette.json` 即可，改完刷新网页就生效。
"""
import json
import os

from em import paths

CFG = os.path.join(paths.CONFIG_DIR, "palette.json")

DEFAULT = [
    {"id": 1, "name": "蓝", "hex": "#3B6FD4"},
    {"id": 2, "name": "绿", "hex": "#2E9E5B"},
    {"id": 3, "name": "橙", "hex": "#E2751B"},
    {"id": 4, "name": "紫", "hex": "#8C52C6"},
    {"id": 5, "name": "粉", "hex": "#D64579"},
    {"id": 6, "name": "深蓝", "hex": "#1F5FA8"},
    {"id": 7, "name": "黄", "hex": "#D9A317"},
    {"id": 8, "name": "青", "hex": "#1B9E96"},
    {"id": 9, "name": "玫红", "hex": "#C22E62"},
    {"id": 10, "name": "靛", "hex": "#5B4BC4"},
    {"id": 11, "name": "浅红", "hex": "#E06868"},
    {"id": 12, "name": "黄绿", "hex": "#7DA81F"},
    {"id": 13, "name": "天蓝", "hex": "#2AA6C4"},
    {"id": 14, "name": "深橙", "hex": "#C4571B"},
    {"id": 15, "name": "灰蓝", "hex": "#6B7688"},
    {"id": 16, "name": "深灰", "hex": "#4A5261"},
]

_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache
    rows = [dict(x) for x in DEFAULT]
    try:
        if os.path.isfile(CFG):
            with open(CFG, "r", encoding="utf-8") as f:
                saved = json.load(f)
            by = {int(x.get("id")): x for x in (saved or []) if x.get("id")}
            for r in rows:
                hit = by.get(r["id"])
                if hit and hit.get("hex"):
                    r["hex"] = hit["hex"]
                if hit and hit.get("name"):
                    r["name"] = hit["name"]
    except Exception:
        pass
    _cache = rows
    return rows


def get() -> list:
    return [dict(x) for x in _load()]


def hex_of(color_id) -> str:
    try:
        n = int(color_id)
    except (TypeError, ValueError):
        return "#8a94a3"
    for r in _load():
        if r["id"] == n:
            return r["hex"]
    return "#8a94a3"


def save(rows: list) -> list:
    """只存被改过的条目，方便人工编辑。"""
    global _cache
    base = {r["id"]: r for r in DEFAULT}
    out = []
    for r in (rows or []):
        try:
            cid = int(r.get("id"))
        except (TypeError, ValueError):
            continue
        b = base.get(cid)
        if not b:
            continue
        if r.get("hex") and r["hex"] != b["hex"] or r.get("name") and r["name"] != b["name"]:
            out.append({"id": cid, "name": r.get("name") or b["name"],
                        "hex": r.get("hex") or b["hex"]})
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _cache = None
    return get()


if __name__ == "__main__":
    for r in get():
        print("%2d %-6s %s" % (r["id"], r["name"], r["hex"]))
