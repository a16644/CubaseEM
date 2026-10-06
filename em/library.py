# -*- coding: utf-8 -*-
"""
技法库 —— 全局库 + 音源分库两层。

文件布局（全部落在 D 盘项目目录内，绝不碰用户的音源目录）：
    config/techniques.json        全局库
    config/libs/<音源名>.json      音源库
    config/settings.json          起始键等偏好
    config/*.json.bak             每次写盘前的上一版

一条技法的主键 = name + group + switch + 键位标识。
"""
import json
import os
import re
import shutil
import time
from typing import Dict, List, Optional, Tuple

from .parsers.common import parse_note, midi_to_name, norm_switch

GLOBAL = "global"
VERSION = 1
_SAFE_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')
_NS_RE = re.compile(r"[\s_\-/.]+")


def safe_filename(s: str) -> str:
    s = _SAFE_RE.sub("_", str(s or "").strip()).strip(" .")
    return s or "default"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def norm_name(s: str) -> str:
    """异写归一：忽略大小写、空格、下划线、连字符、斜杠、点。"""
    return _NS_RE.sub("", str(s or "")).lower()


class Item:
    """库里的一条技法。"""

    def __init__(self, name: str = "", group: int = 0, switch: str = "ks",
                 note: Optional[int] = None, channel: Optional[int] = None,
                 cc_num: Optional[int] = None, cc_val: Optional[int] = None,
                 color: int = 1, description: str = "",
                 tags: List[str] = None, source: str = "", updated: str = ""):
        self.name = str(name or "").strip()
        self.group = int(group or 0)
        self.switch = switch or "ks"
        self.note = note
        self.channel = channel
        self.cc_num = cc_num
        self.cc_val = cc_val
        self.color = int(color or 1)
        self.description = str(description or "")
        self.tags = list(tags or [])
        self.source = str(source or "")
        self.updated = updated or _now()

    # ---- 键位标识：同一 (层, 方式) 下它就是唯一性判据 ----
    @property
    def ident(self) -> str:
        if self.switch in ("ks", "ks2", "ks+ch"):
            return "" if self.note is None else "n%d" % self.note
        if self.switch == "ch":
            return "" if self.channel is None else "c%d" % self.channel
        if self.switch == "cc":
            if self.cc_num is None:
                return ""
            return "cc%d:%d" % (self.cc_num, self.cc_val or 0)
        return ""

    @property
    def id(self) -> str:
        return "%s|%d|%s|%s" % (norm_name(self.name), self.group, self.switch, self.ident)

    @property
    def key_name(self) -> str:
        if self.switch == "ch":
            return "CH%d" % self.channel if self.channel is not None else "-"
        if self.switch == "cc":
            return "CC%d=%s" % (self.cc_num or 0, self.cc_val or 0)
        return midi_to_name(self.note) if self.note is not None else "-"

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "group": self.group, "switch": self.switch,
            "note": self.note, "channel": self.channel,
            "cc_num": self.cc_num, "cc_val": self.cc_val,
            "color": self.color, "description": self.description,
            "tags": self.tags, "source": self.source, "updated": self.updated,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Item":
        return Item(
            name=d.get("name", ""), group=d.get("group", 0),
            switch=d.get("switch", "ks"), note=d.get("note"),
            channel=d.get("channel"), cc_num=d.get("cc_num"),
            cc_val=d.get("cc_val"), color=d.get("color", 1),
            description=d.get("description", ""),
            tags=d.get("tags") or [], source=d.get("source", ""),
            updated=d.get("updated", ""),
        )

    @staticmethod
    def from_row(row: Dict, source: str = "") -> "Item":
        return Item(
            name=row.get("name", ""), group=int(row.get("group", 0) or 0),
            switch=row.get("switch", "ks") or "ks",
            note=row.get("note"), channel=row.get("channel"),
            cc_num=row.get("cc_num"), cc_val=row.get("cc_val"),
            color=int(row.get("color", 1) or 1),
            description=row.get("description", "") or "",
            tags=list(row.get("tags") or []), source=source,
        )

    def to_row(self) -> Dict:
        return {
            "name": self.name, "group": self.group, "switch": self.switch,
            "note": self.note, "channel": self.channel,
            "cc_num": self.cc_num, "cc_val": self.cc_val,
            "color": self.color, "description": self.description,
            "tags": self.tags,
        }


class Lib:
    """双层库的读写与体检。root = 项目根目录。"""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.cfg = os.path.join(self.root, "config")
        self.libs = os.path.join(self.cfg, "libs")
        os.makedirs(self.libs, exist_ok=True)
        self.global_path = os.path.join(self.cfg, "techniques.json")
        self.settings_path = os.path.join(self.cfg, "settings.json")

    # ---------------- 路径 ----------------
    def lib_path(self, source: str) -> str:
        return os.path.join(self.libs, safe_filename(source) + ".json")

    def scope_path(self, scope: str) -> str:
        return self.global_path if scope == GLOBAL else self.lib_path(scope)

    # ---------------- 读写 ----------------
    def _read(self, path: str) -> List[Dict]:
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError):
            # 坏了就别硬撑，保留现场让用户可以回滚
            return []
        return data.get("items", []) if isinstance(data, dict) else []

    def _write(self, path: str, items: List[Dict]):
        if os.path.isfile(path):
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "updated": _now(), "items": items},
                      f, ensure_ascii=False, indent=2)

    def items(self, scope: str) -> List[Item]:
        return [Item.from_dict(d) for d in self._read(self.scope_path(scope))]

    def save(self, scope: str, item: Item, allow_conflict: bool = False) -> Tuple[str, Optional[Item]]:
        """写入一条。返回 (状态, 冲突项)；状态: added / updated / conflict。

        allow_conflict=True 用于批量导入：全局库是跨音源的参考池，
        不同音源用同一个键是常态，不能拦；只有单个音源库内部才必须互斥。
        """
        path = self.scope_path(scope)
        raw = self._read(path)
        by_id = {Item.from_dict(d).id: d for d in raw}
        if item.id in by_id:
            # 已存在同名同层同键的条目：只补字段，来源保留第一次那个，
            # 后来的来源追加进 tags，方便检索时知道"这套键位哪些音源也在用"
            merged = dict(by_id[item.id])
            old_tags = list(merged.get("tags") or [])
            for k, v in item.to_dict().items():
                if v in (None, "", []):
                    continue
                if k == "tags":
                    merged["tags"] = sorted(set(old_tags + list(v)))
                elif k == "source":
                    merged["tags"] = sorted(set(list(merged.get("tags") or [])
                                                + old_tags + ([v] if v else [])))
                else:
                    merged[k] = v
            by_id[item.id] = merged
            self._write(path, list(by_id.values()))
            return "updated", None
        # 单个音源库内部撞键必须拦下，并把空闲键一起给出，用户点一下就能换
        conflict = self.find_conflict(scope, item, raw)
        if conflict is not None and not allow_conflict:
            return "conflict", conflict
        by_id[item.id] = item.to_dict()
        self._write(path, list(by_id.values()))
        return "added", conflict

    def promote(self, item: Item) -> Tuple[str, Optional[Item]]:
        """提到全局库：撞键硬拦。"""
        return self.save(GLOBAL, item)

    def delete(self, scope: str, item_id: str) -> bool:
        path = self.scope_path(scope)
        raw = self._read(path)
        keep = [d for d in raw if Item.from_dict(d).id != item_id]
        if len(keep) == len(raw):
            return False
        self._write(path, keep)
        return True

    def update(self, scope: str, item_id: str, patch: Dict) -> Optional[Item]:
        path = self.scope_path(scope)
        raw = self._read(path)
        hit = None
        for d in raw:
            it = Item.from_dict(d)
            if it.id == item_id:
                hit = it
                break
        if hit is None:
            return None
        for k in ("name", "group", "switch", "note", "channel", "cc_num",
                  "cc_val", "color", "description", "tags", "source"):
            if k in patch:
                setattr(hit, k, patch[k])
        hit.updated = _now()
        self.delete(scope, item_id)
        self.save(scope, hit)
        return hit

    # ---------------- 查重 ----------------
    def find_conflict(self, scope: str, item: Item, raw: List[Dict] = None) -> Optional[Item]:
        """同层同方式同键位、但名字不同 -> 硬冲突。"""
        raw = self._read(self.scope_path(scope)) if raw is None else raw
        for d in raw:
            other = Item.from_dict(d)
            if other.id == item.id or not other.ident or not item.ident:
                continue
            if (other.group == item.group and other.switch == item.switch
                    and other.ident == item.ident
                    and norm_name(other.name) != norm_name(item.name)):
                return other
        return None

    def find_same_name(self, scope: str, item: Item) -> List[Item]:
        """同名同层但键位不同 -> 软冲突，提示用。"""
        return [it for it in self.items(scope)
                if norm_name(it.name) == norm_name(item.name)
                and it.group == item.group and it.switch == item.switch
                and it.ident != item.ident]

    def used_keys(self, scope: str, group: int, switch: str) -> set:
        out = set()
        for it in self.items(scope):
            if it.group == group and it.switch == switch and it.note is not None:
                out.add(it.note)
        return out

    def free_key(self, scope: str, group: int, switch: str, start: int = None) -> Optional[int]:
        if switch not in ("ks", "ks2", "ks+ch"):
            return None
        if start is None:
            start = int(self.settings().get("start_key", 24))
        used = self.used_keys(scope, group, switch)
        used |= self.used_keys(GLOBAL, group, switch)
        for i in range(0, 128):
            for cand in ((start + i), (start - i)):
                if 0 <= cand <= 127 and cand not in used:
                    return cand
        return None

    # ---------------- 检索 ----------------
    def search(self, q: str, source: str = "") -> List[Dict]:
        """本音源库优先，再全局库；标记 _scope 方便界面分组。"""
        q = (q or "").strip()
        nq = norm_name(q)
        out, seen = [], set()
        scopes = []
        if source:
            scopes.append((source, "lib"))
        scopes.append((GLOBAL, "global"))
        for scope, kind in scopes:
            for it in self.items(scope):
                if q and nq not in norm_name(it.name) and nq not in norm_name(it.description) \
                        and not any(nq in norm_name(t) for t in it.tags):
                    continue
                key = it.id
                if key in seen:
                    continue
                seen.add(key)
                d = it.to_dict()
                d["_id"] = it.id
                d["_scope"] = kind
                d["_key"] = it.key_name
                out.append(d)
        out.sort(key=lambda d: (d["_scope"] != "lib", d["group"], d["name"]))
        return out

    # ---------------- 库体检 ----------------
    def audit(self, scope: str) -> Dict[str, List[Dict]]:
        raw = self._read(self.scope_path(scope))
        items = [Item.from_dict(d) for d in raw]
        res = {"hard": [], "soft": [], "alias": [], "broken": [], "exact": []}

        seen_id = {}
        for it in items:
            seen_id.setdefault(it.id, []).append(it)
        for k, v in seen_id.items():
            if len(v) > 1:
                res["exact"].append({"name": v[0].name, "group": v[0].group,
                                     "count": len(v), "key": v[0].key_name})

        for i, a in enumerate(items):
            if not a.ident:
                res["broken"].append({"id": a.id, "name": a.name, "group": a.group,
                                      "switch": a.switch, "key": "-"})
                continue
            for b in items[i + 1:]:
                if not b.ident or a.id == b.id:
                    continue
                # 全局库是跨音源参考池，不同音源用同一个键是常态 —— 只有同一个音源
                # 内部撞键才算真冲突，否则 25 个音源会互相"打架"，报告全是噪音
                if scope == GLOBAL and not (set(a.tags) & set(b.tags)):
                    continue
                same_slot = (a.group == b.group and a.switch == b.switch and a.ident == b.ident)
                if same_slot and norm_name(a.name) != norm_name(b.name):
                    res["hard"].append({
                        "a": {"id": a.id, "name": a.name, "key": a.key_name},
                        "b": {"id": b.id, "name": b.name, "key": b.key_name},
                        "group": a.group, "switch": a.switch,
                    })
                elif (norm_name(a.name) == norm_name(b.name) and a.group == b.group
                      and a.switch == b.switch and a.ident != b.ident):
                    res["soft"].append({
                        "name": a.name, "group": a.group, "switch": a.switch,
                        "keys": [a.key_name, b.key_name],
                        "ids": [a.id, b.id],
                    })
        for k in ("hard", "soft"):
            res[k] = res[k][:200]

        buckets = {}
        for it in items:
            buckets.setdefault(norm_name(it.name), []).append(it)
        for k, v in buckets.items():
            spellings = sorted({x.name for x in v})
            if len(spellings) > 1:
                res["alias"].append({"norm": k, "spellings": spellings,
                                     "count": len(v)})
        return res

    def rename_spelling(self, scope: str, target: str, ids: List[str]) -> int:
        """把一批异写统一成同一个写法。"""
        path = self.scope_path(scope)
        raw = self._read(path)
        n = 0
        for d in raw:
            it = Item.from_dict(d)
            if it.id in ids:
                d["name"] = target
                n += 1
        if n:
            self._write(path, raw)
        return n

    # ---------------- 设置 ----------------
    def settings(self) -> Dict:
        if not os.path.isfile(self.settings_path):
            return {"start_key": 24}
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {"start_key": 24}

    def set_settings(self, patch: Dict):
        s = self.settings()
        s.update(patch or {})
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)

    # ---------------- 冷启动导入 ----------------
    def import_items(self, scope: str, items: List[Item]) -> Dict:
        """批量导入。全局库允许不同音源共用键位，所以这里不拦冲突。"""
        added = updated = skipped = 0
        for it in items:
            st, _ = self.save(scope, it, allow_conflict=True)
            if st == "added":
                added += 1
            elif st == "updated":
                updated += 1
            else:
                skipped += 1
        return {"added": added, "updated": updated, "skipped": skipped,
                "total": len(items)}

    def stats(self) -> Dict:
        g = len(self._read(self.global_path))
        libs = {}
        if os.path.isdir(self.libs):
            for fn in sorted(os.listdir(self.libs)):
                if fn.endswith(".json"):
                    libs[fn[:-5]] = len(self._read(os.path.join(self.libs, fn)))
        return {"global": g, "libs": libs}
