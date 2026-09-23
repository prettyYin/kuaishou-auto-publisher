# -*- coding: utf-8 -*-
"""运行进度（断点续跑）与状态持久化。"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

STATUS_PENDING = "待处理"
STATUS_DRY_RUN = "演练未发布"
STATUS_PUBLISHED = "已发布"
STATUS_UNCERTAIN = "发布结果不确定"
STATUS_FAILED = "失败"
STATUS_SKIPPED = "已跳过"


class RunState:
    """以 (账号, 序号) 为键记录每条视频的处理结果。"""

    def __init__(self, path: Path, date_str: str) -> None:
        self.path = Path(path)
        self.date = date_str
        self.data: Dict[str, Any] = {"date": date_str, "items": {}}
        self._lock = threading.RLock()

    @classmethod
    def load(cls, run_dir: Path, date_str: str) -> "RunState":
        path = Path(run_dir) / ("state_%s.json" % date_str)
        state = cls(path, date_str)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    loaded.setdefault("items", {})
                    loaded["date"] = loaded.get("date") or date_str
                    state.data = loaded
                    state._migrate()
            except Exception:
                pass
        return state

    def _migrate(self) -> None:
        """把旧版按序号存的记录改成按「账号+路径」存（有路径的才迁移）。"""
        items = self.data.get("items") or {}
        migrated: Dict[str, Any] = {}
        for key, entry in items.items():
            if not isinstance(entry, dict):
                continue
            account = entry.get("account") or ""
            try:
                index = int(entry.get("index", 0))
            except Exception:
                index = 0
            new_key = self.make_key(account, index, entry.get("path") or "")
            migrated[new_key] = entry
        self.data["items"] = migrated

    @staticmethod
    def make_key(account: str, index: int, path: str = "") -> str:
        """记录键：优先用「账号 + 完整路径」，没有路径时才退回「账号 + 序号」。

        用路径作键可以彻底避免"换了素材文件夹后序号串号"导致把没发过的视频当成已发布。
        """
        path = (path or "").strip()
        if path:
            return "%s::%s" % (account, path.lower())
        return "%s::#%d" % (account, index)

    @staticmethod
    def key(account: str, index: int) -> str:
        return RunState.make_key(account, index)

    def item(
        self, account: str, index: int, file_name: str = "", copy_text: str = "", path: str = ""
    ) -> Dict[str, Any]:
        with self._lock:
            key = self.make_key(account, index, path)
            entry = self.data["items"].get(key)
            if entry is None:
                entry = {
                    "account": account,
                    "index": index,
                    "file": file_name,
                    "path": path,
                    "copy": copy_text,
                    "publish_mode": "立即发布",
                    "publish_at": "",
                    "scheduled_status": "",
                    "skip_reason": "",
                    "publish_status": STATUS_PENDING,
                    "work_url": "",
                    "rename_status": "",
                    "seconds": 0,
                    "updated": "",
                    "note": "",
                }
                self.data["items"][key] = entry
            elif path and (entry.get("path") or "").strip().lower() != path.strip().lower():
                # 同一个账号+序号，但文件路径变了：说明换了一批视频，重置这条记录
                for transient_key in list(entry.keys()):
                    if str(transient_key).startswith("_"):
                        entry.pop(transient_key, None)
                entry.update(
                    {
                        "account": account,
                        "index": index,
                        "path": path,
                        "publish_mode": "立即发布",
                        "publish_at": "",
                        "scheduled_status": "",
                        "skip_reason": "",
                        "publish_status": STATUS_PENDING,
                        "work_url": "",
                        "rename_status": "",
                        "seconds": 0,
                        "note": "",
                    }
                )
            if file_name:
                entry["file"] = file_name
            if copy_text:
                entry["copy"] = copy_text
            if path:
                entry["path"] = path
            return entry

    def set_transient(self, account: str, index: int, path: str = "", **fields: Any) -> Dict[str, Any]:
        """写入只在本次运行内存里使用的字段（例如作者声明），不落盘。"""
        with self._lock:
            entry = self.item(account, index, path=path)
            for key, value in fields.items():
                entry[key if str(key).startswith("_") else "_" + str(key)] = value
            return entry

    def is_published(self, account: str, index: int) -> bool:
        entry = self.data["items"].get(self.key(account, index))
        return bool(entry) and entry.get("publish_status") == STATUS_PUBLISHED

    def is_published_file(self, account: str, file_name: str) -> bool:
        """按文件名判断是否已发布：换素材文件夹后也不会误判。"""
        if not file_name:
            return False
        for entry in self.data["items"].values():
            if entry.get("account") == account and entry.get("file") == file_name:
                return entry.get("publish_status") == STATUS_PUBLISHED
        return False

    def is_published_path(self, account: str, path: str) -> bool:
        """按完整路径判断是否已发布：同名文件换目录后会被当成新的一条。"""
        if not path:
            return False
        for entry in self.data["items"].values():
            if entry.get("account") == account and entry.get("path") == path:
                return entry.get("publish_status") == STATUS_PUBLISHED
        return False

    def reset(self) -> None:
        with self._lock:
            self.data["items"] = {}
            self.save()

    def clear_paths(self, account: str, paths) -> int:
        """清掉指定文件的记录，让它们重新发布一遍。"""
        with self._lock:
            targets = set(paths or [])
            removed = 0
            for key, entry in list(self.data["items"].items()):
                if entry.get("account") == account and entry.get("path") in targets:
                    self.data["items"].pop(key, None)
                    removed += 1
            if removed:
                self.save()
            return removed

    def is_renamed(self, account: str, index: int) -> bool:
        entry = self.data["items"].get(self.key(account, index))
        return bool(entry) and entry.get("rename_status") == "已改名"

    def mark(self, account: str, index: int, path: str = "", **fields: Any) -> Dict[str, Any]:
        with self._lock:
            entry = self.item(account, index, path=path)
            entry.update(fields)
            entry["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save()
            return entry

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            sanitized = {
                "date": self.data.get("date", ""),
                "items": {
                    key: {
                        field: value
                        for field, value in entry.items()
                        if not str(field).startswith("_")
                    }
                    for key, entry in (self.data.get("items") or {}).items()
                    if isinstance(entry, dict)
                },
            }
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(sanitized, fh, ensure_ascii=False, indent=2)
            tmp.replace(self.path)

    def items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.data["items"].values())

    def summary(self) -> str:
        items = self.items()
        published = sum(1 for it in items if it.get("publish_status") == STATUS_PUBLISHED)
        scheduled = sum(
            1
            for it in items
            if it.get("publish_status") == STATUS_PUBLISHED and it.get("publish_at")
        )
        renamed = sum(1 for it in items if it.get("rename_status") == "已改名")
        failed = sum(1 for it in items if it.get("publish_status") in (STATUS_FAILED, STATUS_UNCERTAIN))
        suffix = "（含定时 %d 条）" % scheduled if scheduled else ""
        return "已发布 %d 条%s，已改名 %d 条，异常 %d 条" % (published, suffix, renamed, failed)
