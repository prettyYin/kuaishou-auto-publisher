# -*- coding: utf-8 -*-
"""读取本地视频时长（不依赖 ffmpeg，直接解析 mp4/mov 的 mvhd 盒）。"""
from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Optional

_TIME_RE = re.compile(r"(?:^|[^\d])(\d{1,3}):([0-5]\d)(?:[^\d]|$)")
_DATETIME_RE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}")


def extract_duration_seconds(text: str) -> Optional[int]:
    """从页面文字里提取视频时长（mm:ss）。

    会先剔除「2026-09-17 10:45:43」这类创建时间，避免把时间当成时长。
    """
    if not text:
        return None
    cleaned = _DATETIME_RE.sub(" ", str(text))
    match = _TIME_RE.search(cleaned)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def duration_seconds(path) -> Optional[float]:
    """返回视频时长（秒）；解析不了就返回 None。"""
    try:
        size = Path(path).stat().st_size
        with open(path, "rb") as handle:
            return _walk(handle, 0, size, 0)
    except Exception:
        return None


def _walk(handle, start: int, end: int, depth: int) -> Optional[float]:
    pos = start
    while pos + 8 <= end:
        handle.seek(pos)
        head = handle.read(8)
        if len(head) < 8:
            return None
        size = struct.unpack(">I", head[:4])[0]
        box_type = head[4:8]
        if size == 1:
            size = struct.unpack(">Q", handle.read(8))[0]
        elif size == 0:
            size = end - pos
        if size < 8:
            return None
        if box_type == b"mvhd":
            return _parse_mvhd(handle)
        if box_type in (b"moov", b"trak", b"mdia") and depth < 5:
            found = _walk(handle, pos + 8, pos + size, depth + 1)
            if found is not None:
                return found
        pos += size
    return None


def _parse_mvhd(handle) -> Optional[float]:
    head = handle.read(4)  # version + flags
    if len(head) < 4:
        return None
    version = head[0]
    if version == 1:
        handle.read(16)
        raw = handle.read(12)
        if len(raw) < 12:
            return None
        timescale, duration = struct.unpack(">IQ", raw)
    else:
        handle.read(8)
        raw = handle.read(8)
        if len(raw) < 8:
            return None
        timescale, duration = struct.unpack(">II", raw)
    if not timescale:
        return None
    return duration / float(timescale)
