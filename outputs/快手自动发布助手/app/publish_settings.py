# -*- coding: utf-8 -*-
"""发布设置模型：作者声明、定时发布时间和后续可扩展字段。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

AUTHOR_DECLARATION_OPTIONS: Tuple[str, ...] = (
    "内容为AI生成",
    "演绎情节，仅供娱乐",
    "个人观点，仅供参考",
    "素材来源于网络",
)
AUTHOR_NONE_LABEL = "不设置"

PREVIEW_COLUMNS = ("序号", "文件名", "广告语", "作者声明", "发布时间", "状态")

# 统一的发布字段清单。以后新增关联热点、添加地点、作者服务时，
# 只需要在这里增加定义，界面和发布流程都按同一份清单工作。
FIELD_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "author_statement",
        "label": "作者声明",
        "group": "常用设置",
        "kind": "select",
        "options": AUTHOR_DECLARATION_OPTIONS,
        "scope": "per_video",
        "batch_apply": True,
        "default": "",
        "enabled": True,
    },
    {
        "key": "publish_at",
        "label": "发布时间",
        "group": "常用设置",
        "kind": "datetime",
        "options": (),
        "scope": "per_video",
        "batch_apply": True,
        "default": "",
        "enabled": True,
    },
    {
        "key": "related_hotspot",
        "label": "关联热点",
        "group": "更多设置",
        "kind": "search_select",
        "options": (),
        "scope": "per_video",
        "batch_apply": True,
        "default": "",
        "enabled": False,
    },
    {
        "key": "add_location",
        "label": "添加地点",
        "group": "更多设置",
        "kind": "search_select",
        "options": (),
        "scope": "per_video",
        "batch_apply": True,
        "default": "",
        "enabled": False,
    },
    {
        "key": "author_service",
        "label": "作者服务",
        "group": "更多设置",
        "kind": "composite_select",
        "options": (),
        "scope": "per_video",
        "batch_apply": True,
        "default": "",
        "enabled": False,
    },
]


def default_settings() -> Dict[str, Any]:
    return {"author_statement": "", "publish_at": ""}


def setting_key(account: str, path: str) -> str:
    return "%s::%s" % (account or "", str(path or "").lower())


def default_schedule_time(now: Optional[datetime] = None) -> datetime:
    """定时发布默认值：当前时间 61 分钟后（秒归零，避开平台 1 小时边界）。"""
    value = (now or datetime.now()).replace(second=0, microsecond=0)
    return value + timedelta(minutes=61)


def schedule_time_values(value: Any, column_count: int) -> List[str]:
    parsed = parse_publish_at(value)
    if parsed is None:
        return []
    values = ["%02d" % parsed.hour, "%02d" % parsed.minute, "%02d" % parsed.second]
    return values[: max(min(int(column_count), 3), 0)]


def month_number(text: Any) -> int:
    match = re.search(r"(\d{1,2})", str(text or ""))
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def year_number(text: Any) -> int:
    match = re.search(r"(\d{4})", str(text or ""))
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def path_text(video: Any) -> str:
    if hasattr(video, "__fspath__"):
        try:
            return str(video.__fspath__())
        except Exception:
            pass
    return str(video)


def settings_for_videos(
    account: str,
    videos: Iterable[Any],
    settings_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    saved = settings_map or {}
    result: List[Dict[str, Any]] = []
    for video in videos:
        item = dict(default_settings())
        item.update(saved.get(setting_key(account, path_text(video))) or {})
        result.append(item)
    return result


def parse_publish_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text, fmt).replace(microsecond=0)
        except ValueError:
            continue
    return None


def normalize_publish_at(value: Any) -> str:
    parsed = parse_publish_at(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def format_publish_at(value: Any) -> str:
    parsed = parse_publish_at(value)
    if parsed is None:
        return "立即发布"
    return parsed.strftime("%Y-%m-%d %H:%M")


def summarize_author(value: Any) -> str:
    text = str(value or "").strip()
    return text or AUTHOR_NONE_LABEL


def validate_publish_at(
    value: Any,
    now: Optional[datetime] = None,
    min_lead_minutes: int = 60,
    max_days: int = 14,
) -> str:
    """返回空字符串表示通过，否则返回给用户看的错误原因。"""
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = parse_publish_at(text)
    if parsed is None:
        return "定时时间格式不对，请选择完整的年月日时分"
    current = (now or datetime.now()).replace(tzinfo=None, microsecond=0)
    if parsed <= current:
        return "定时时间必须晚于当前时间"
    remaining = parsed - current
    # 平台实际只要求晚于当前时间 1 分钟（60 秒）；这里按精确秒数判断。
    if remaining.total_seconds() < max(int(min_lead_minutes), 0) * 60:
        return "定时时间至少要比现在晚 %d 分钟" % int(min_lead_minutes)
    if remaining > timedelta(days=max(int(max_days), 1)):
        return "定时时间不能超过 %d 天" % int(max_days)
    return ""


def run_with_retries(action: Callable[[], Any], retries: int = 2) -> Tuple[bool, str]:
    """执行动作；初次失败后再重试 retries 次。返回 (是否成功, 最后错误)。"""
    last_error = ""
    for attempt in range(max(int(retries), 0) + 1):
        try:
            action()
            return True, ""
        except Exception as exc:
            last_error = str(exc) or type(exc).__name__
    return False, last_error


def has_scheduled(settings_map: Dict[str, Dict[str, Any]]) -> bool:
    for value in (settings_map or {}).values():
        if str((value or {}).get("publish_at") or "").strip():
            return True
    return False


def field_groups(definitions: Optional[Iterable[Dict[str, Any]]] = None) -> List[Tuple[str, List[Dict[str, Any]]]]:
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    for definition in definitions or FIELD_DEFINITIONS:
        if not definition.get("enabled", True):
            continue
        group = str(definition.get("group") or "其他设置")
        for name, items in groups:
            if name == group:
                items.append(definition)
                break
        else:
            groups.append((group, [definition]))
    return groups


def preview_columns() -> Tuple[str, ...]:
    return PREVIEW_COLUMNS


def setting_summary(settings: Dict[str, Any]) -> str:
    author = summarize_author((settings or {}).get("author_statement"))
    publish = format_publish_at((settings or {}).get("publish_at"))
    return "%s · %s" % (author, publish)
