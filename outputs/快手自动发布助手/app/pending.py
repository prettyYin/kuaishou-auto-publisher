# -*- coding: utf-8 -*-
"""定时发布后的金牛改名待办台账。"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as cfgmod


class PendingRenameStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else (cfgmod.RUN_DIR / "pending_rename.json")
        self.data: Dict[str, Any] = {"entries": []}
        self._lock = threading.RLock()

    def load(self) -> "PendingRenameStore":
        with self._lock:
            if not self.path.exists():
                return self
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("entries"), list):
                    self.data = loaded
            except Exception:
                self.data = {"entries": []}
            return self

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.data.get("entries") or [])

    def add(
        self,
        account: str,
        file_name: str,
        copy_text: str = "",
        publish_at: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "account": str(account or ""),
                "file": str(file_name or ""),
                "copy": str(copy_text or ""),
                "publish_at": str(publish_at or ""),
                "note": str(note or ""),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            items = self.data.setdefault("entries", [])
            for index, old in enumerate(items):
                if old.get("account") == entry["account"] and old.get("file") == entry["file"]:
                    items[index] = entry
                    self.save()
                    return entry
            items.append(entry)
            self.save()
            return entry

    def resolve(self, account: str, file_names) -> int:
        with self._lock:
            targets = {str(name or "") for name in (file_names or []) if str(name or "")}
            if not targets:
                return 0
            items = self.data.get("entries") or []
            kept = [
                item
                for item in items
                if not (str(item.get("account") or "") == str(account or "") and str(item.get("file") or "") in targets)
            ]
            removed = len(items) - len(kept)
            if removed:
                self.data["entries"] = kept
                self.save()
            return removed

    def summary(self) -> str:
        with self._lock:
            items = self.entries()
            if not items:
                return "没有待改名的金牛素材"
            return "有 %d 条定时发布的素材待手动改金牛素材名" % len(items)

    def clear_all(self) -> int:
        """用户确认已手动改完名，或重置今日进度时清空全部待办。"""
        with self._lock:
            removed = len(self.data.get("entries") or [])
            if removed:
                self.data["entries"] = []
                self.save()
            return removed
