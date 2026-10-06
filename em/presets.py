# -*- coding: utf-8 -*-
"""
组合模板库：config/combo_presets.json

一个模板 = 一组「组合槽位」的结构描述，可以有很多个，随时套用。
模板只存结构（哪些条件层、每个组合的成员与可覆盖的输出键），不存具体技法名。
"""
import json
import os
import shutil
import time
from typing import Dict, List

from .library import safe_filename  # noqa: F401  (保持依赖清晰，safe_filename 复用)
from .model import Cond


class Presets:

    def __init__(self, root: str):
        self.path = os.path.join(os.path.abspath(root), "config", "combo_presets.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _read(self) -> List[Dict]:
        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError):
            return []
        return data.get("presets", []) if isinstance(data, dict) else []

    def _write(self, presets: List[Dict]):
        if os.path.isfile(self.path):
            try:
                shutil.copy2(self.path, self.path + ".bak")
            except OSError:
                pass
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "presets": presets}, f, ensure_ascii=False, indent=2)

    def list(self) -> List[Dict]:
        return self._read()

    def get(self, name: str) -> Dict:
        for p in self._read():
            if p.get("name") == name:
                return p
        return {}

    def save(self, name: str, layers: List[int], combos: List[Dict],
             prefix: str = "插槽") -> Dict:
        presets = self._read()
        payload = {
            "name": name,
            "layers": [int(x) for x in layers or []],
            "prefix": prefix or "插槽",
            "combos": combos or [],
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for i, p in enumerate(presets):
            if p.get("name") == name:
                presets[i] = payload
                break
        else:
            presets.append(payload)
        self._write(presets)
        return payload

    def delete(self, name: str) -> bool:
        presets = self._read()
        keep = [p for p in presets if p.get("name") != name]
        if len(keep) == len(presets):
            return False
        self._write(keep)
        return True

    @staticmethod
    def combos_to_conds(combos: List[Dict]) -> List[List[Cond]]:
        """模板里的组合 -> 条件对象，供生成器使用。"""
        out = []
        for c in combos or []:
            conds = []
            for m in c.get("members", []) or []:
                conds.append(Cond(group=int(m.get("group", 0) or 0),
                                  description=str(m.get("description", "") or ""),
                                  note=m.get("note")))
            if conds:
                out.append(conds)
        return out
