# -*- coding: utf-8 -*-
"""视频目录扫描与顺序计算。"""
from __future__ import annotations

import os
import re
import sys
from functools import cmp_to_key
from pathlib import Path
from typing import List

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg"}
_NUM_RE = re.compile(r"(\d+)")


def _explorer_comparator():
    """用 Windows 资源管理器同款排序（StrCmpLogicalW），中文按拼音、数字按数值。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes

        shlwapi = ctypes.windll.shlwapi
        shlwapi.StrCmpLogicalW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        shlwapi.StrCmpLogicalW.restype = ctypes.c_int
        return lambda a, b: shlwapi.StrCmpLogicalW(a, b)
    except Exception:
        return None


_EXPLORER = _explorer_comparator()


def natural_key(path: Path | str):
    """排序键：和资源管理器看到的顺序一致（Windows 用系统排序接口）。"""
    name = Path(str(path)).name.lower()
    if _EXPLORER is not None:
        return cmp_to_key(lambda a, b: _EXPLORER(a.lower(), b.lower()))(name)
    key = []
    for part in _NUM_RE.split(name):
        if part.isdigit():
            key.append((1, int(part), ""))
        else:
            key.append((0, 0, part))
    return key


def list_videos(folder: str | Path) -> List[Path]:
    """按文件名自然排序，列出目录内的视频文件。"""
    folder = Path(str(folder))
    if not folder.is_dir():
        return []
    files = [
        item
        for item in folder.iterdir()
        if item.is_file() and item.suffix.lower() in VIDEO_EXTS and not item.name.startswith("~$")
    ]
    files.sort(key=natural_key)
    return files


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return "%.1f%s" % (num_bytes, unit)
        num_bytes /= 1024.0
    return "%.1fTB" % num_bytes


def folder_summary(videos: List[Path]) -> str:
    if not videos:
        return "0 个视频"
    total = 0
    for item in videos:
        try:
            total += os.path.getsize(item)
        except OSError:
            pass
    return "%d 个视频，共 %s" % (len(videos), human_size(total))


def build_plan(videos: List[Path], copies: List[str]) -> List[dict]:
    """按顺序把视频和广告语配对。"""
    plan = []
    for index, video in enumerate(videos):
        plan.append(
            {
                "index": index,
                "file": video.name,
                "path": str(video),
                "copy": copies[index] if index < len(copies) else "",
            }
        )
    return plan


def compare_counts(video_count: int, copy_count: int) -> str:
    if video_count == 0 and copy_count == 0:
        return "空"
    if video_count == copy_count:
        return "匹配"
    return "不匹配：视频 %d 条 / 广告语 %d 条" % (video_count, copy_count)
