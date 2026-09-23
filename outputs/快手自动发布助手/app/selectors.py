# -*- coding: utf-8 -*-
"""页面选择器解析：每个动作用一组候选规则依次尝试，尽量抗改版。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .config import SELECTORS_PATH


class PageStructureError(RuntimeError):
    """页面上找不到预期元素（页面结构可能变了）。"""


def build_locator(scope, candidate: Dict[str, Any]):
    """按一条候选规则构造 Locator。"""
    if isinstance(candidate, str):
        candidate = {"css": candidate}
    if "css" in candidate:
        locator = scope.locator(candidate["css"])
    elif "text" in candidate:
        locator = scope.get_by_text(candidate["text"], exact=bool(candidate.get("exact", False)))
    elif "placeholder" in candidate:
        locator = scope.get_by_placeholder(candidate["placeholder"])
    elif "label" in candidate:
        locator = scope.get_by_label(candidate["label"])
    elif "role" in candidate:
        locator = scope.get_by_role(
            candidate["role"], name=candidate.get("name"), exact=bool(candidate.get("exact", False))
        )
    elif "testid" in candidate:
        locator = scope.get_by_test_id(candidate["testid"])
    else:
        raise ValueError("无法识别的选择器规则：%r" % (candidate,))
    if candidate.get("nth") is not None:
        locator = locator.nth(int(candidate["nth"]))
    elif candidate.get("last"):
        locator = locator.last
    else:
        locator = locator.first
    return locator


def _scopes(scope):
    """页面 + 它的所有 iframe（快手后台的表单常常嵌在 iframe 里）。"""
    yield scope
    frames = getattr(scope, "frames", None)
    if not frames:
        return
    main = getattr(scope, "main_frame", None)
    for frame in frames:
        if frame is scope or frame is main:
            continue
        yield frame


def find_any(
    scope,
    candidates: Sequence[Dict[str, Any]],
    timeout: float = 10.0,
    need_visible: bool = True,
    poll: float = 0.4,
):
    """在一组候选规则里找到第一个可用元素，返回 Locator 或 None（主页面优先，其次各 iframe）。"""
    if not candidates:
        return None
    deadline = time.time() + max(timeout, 0.1)
    while True:
        for current in _scopes(scope):
            for candidate in candidates:
                try:
                    locator = build_locator(current, candidate)
                    if locator.count() == 0:
                        continue
                    if need_visible and not locator.is_visible():
                        continue
                    return locator
                except Exception:
                    continue
        if time.time() >= deadline:
            return None
        time.sleep(poll)


def exists_any(scope, candidates: Sequence[Dict[str, Any]], need_visible: bool = True) -> bool:
    return find_any(scope, candidates, timeout=0.8, need_visible=need_visible) is not None


def find_list(scope, candidates: Sequence[Dict[str, Any]], min_count: int = 1):
    """找一个"列表"型元素（返回包含多个元素的 Locator，而不是 first）。"""
    for candidate in candidates or []:
        try:
            if isinstance(candidate, str):
                candidate = {"css": candidate}
            if "css" in candidate:
                locator = scope.locator(candidate["css"])
            elif "text" in candidate:
                locator = scope.get_by_text(candidate["text"], exact=bool(candidate.get("exact", False)))
            elif "role" in candidate:
                locator = scope.get_by_role(candidate["role"], name=candidate.get("name"))
            else:
                continue
            if locator.count() >= min_count:
                return locator
        except Exception:
            continue
    return None


def click_any(scope, candidates, timeout: float = 10.0, force: bool = False):
    locator = find_any(scope, candidates, timeout=timeout)
    if locator is None:
        raise PageStructureError(
            "找不到可点击的元素：%s" % json.dumps(candidates, ensure_ascii=False)[:200]
        )
    locator.click(force=force, timeout=15000)
    return locator


def set_text(locator, text: str, delay: int = 12) -> None:
    """兼容 input / textarea / contenteditable 三种输入框。"""
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
    except Exception:
        tag = "input"
    try:
        editable = bool(locator.evaluate("el => el.isContentEditable === true"))
    except Exception:
        editable = False
    if tag in ("input", "textarea"):
        locator.fill(text, timeout=8000)
        return
    if editable:
        locator.click(timeout=8000)
        try:
            locator.press("Control+a", timeout=5000)
        except Exception:
            pass
        try:
            locator.press_sequentially(text, delay=delay, timeout=15000)
        except Exception:
            locator.type(text, delay=delay, timeout=15000)
        return
    locator.fill(text, timeout=8000)


def fill_any(scope, candidates, text: str, timeout: float = 10.0):
    locator = find_any(scope, candidates, timeout=timeout)
    if locator is None:
        raise PageStructureError(
            "找不到输入框：%s" % json.dumps(candidates, ensure_ascii=False)[:200]
        )
    set_text(locator, text)
    return locator


def set_files_any(scope, candidates, files: Sequence[str], timeout: float = 15.0):
    locator = find_any(scope, candidates, timeout=timeout, need_visible=False)
    if locator is None:
        raise PageStructureError("找不到文件选择框（input[type=file]）")
    locator.set_input_files(list(files))
    return locator


def text_any(scope, candidates, timeout: float = 5.0) -> str:
    locator = find_any(scope, candidates, timeout=timeout)
    if locator is None:
        return ""
    try:
        return (locator.inner_text() or "").strip()
    except Exception:
        return ""


class Selectors:
    """selectors.json 的读取与分组。"""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data or {}

    @classmethod
    def load(cls, path: Path | str = SELECTORS_PATH) -> "Selectors":
        path = Path(path)
        if not path.exists():
            return cls({})
        with open(path, "r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def group(self, name: str) -> Dict[str, Any]:
        return self.data.get(name) or {}

    def get(self, group: str, key: str) -> List[Dict[str, Any]]:
        value = self.group(group).get(key) or []
        if isinstance(value, (str, dict)):
            value = [value]
        return list(value)

    def merged(self, group: str, key: str, fallback: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """配置里的候选优先，随后追加内置兜底候选。"""
        return list(self.get(group, key)) + list(fallback)
