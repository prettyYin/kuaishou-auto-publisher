# -*- coding: utf-8 -*-
"""当天广告语的本地保存：关掉工具再打开也不会丢。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from . import config as cfgmod


class CopyStore:
    def __init__(self, path: Optional[Path] = None, date_str: Optional[str] = None) -> None:
        self.date = date_str or datetime.now().strftime("%Y-%m-%d")
        self.path = Path(path) if path else (cfgmod.RUN_DIR / ("copies_%s.json" % self.date))
        self.data: Dict[str, Any] = {"date": self.date, "accounts": {}}

    def load(self) -> "CopyStore":
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict) and isinstance(loaded.get("accounts"), dict):
                    self.data = loaded
                    self.data.setdefault("date", self.date)
            except Exception:
                pass
        return self

    def get(self, account_name: str) -> Dict[str, Any]:
        entry = self.data["accounts"].get(account_name) or {}
        return {
            "raw": entry.get("raw", ""),
            "strip_index": bool(entry.get("strip_index", False)),
            "batch": bool(entry.get("batch", False)),
        }

    def set(self, account_name: str, raw: str, strip_index: bool = False, batch: bool = False) -> None:
        if not account_name:
            return
        self.data["accounts"][account_name] = {
            "raw": raw or "",
            "strip_index": bool(strip_index),
            "batch": bool(batch),
        }
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            tmp.replace(self.path)
        except Exception:
            pass

    def summary(self) -> str:
        filled = sum(1 for name, entry in self.data["accounts"].items() if (entry.get("raw") or "").strip())
        return "已保存 %d 个账号的广告语" % filled
