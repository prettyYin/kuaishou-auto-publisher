# -*- coding: utf-8 -*-
"""广告语清单解析。"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List

_INDEX_RE = re.compile(r"^\s*(\d{1,3})\s*[\.、\)）:：]\s*(?=\S)")
_HEADER_RE = re.compile(r"^\s*[【\[]([^】\]]{1,20})[】\]]\s*$")
_ACCOUNT_HEADER_RE = re.compile(r"^\s*(账号|账户|号|昵称|账号名)[:：].{0,20}$")


def parse_copies(text: str, strip_index: bool = False, drop_headers: bool = True) -> List[str]:
    """把粘贴的文本拆成广告语列表。

    - 每行一条，空行忽略
    - strip_index=True 时去掉行首的 "1." / "1、" / "1)" 之类序号
    - drop_headers=True 时忽略 "【账号A】"、"账号：xxx" 这类标题行
    """
    if not text:
        return []
    copies: List[str] = []
    for raw_line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip().strip("\u200b").strip()
        if not line:
            continue
        if drop_headers and (_HEADER_RE.match(line) or _ACCOUNT_HEADER_RE.match(line)):
            continue
        if strip_index:
            line = _INDEX_RE.sub("", line, count=1).strip()
        if line:
            copies.append(line)
    return copies


def find_duplicates(copies: List[str]) -> Dict[str, int]:
    counter = Counter(copies)
    return {text: count for text, count in counter.items() if count > 1}


def validate(copies: List[str], video_count: int) -> Dict[str, object]:
    """返回校验结果，供界面显示。"""
    result: Dict[str, object] = {
        "copy_count": len(copies),
        "video_count": video_count,
        "ok": False,
        "message": "",
    }
    if video_count == 0:
        result["message"] = "素材目录里没有视频文件"
        return result
    if not copies:
        result["message"] = "还没有粘贴广告语"
        return result
    if len(copies) != video_count:
        result["message"] = "数量不一致：视频 %d 条 / 广告语 %d 条" % (video_count, len(copies))
        return result
    if any(not item.strip() for item in copies):
        result["message"] = "存在空白广告语"
        return result
    duplicates = find_duplicates(copies)
    result["ok"] = True
    if duplicates:
        dup_text = "；".join("%s(×%d)" % (k, v) for k, v in list(duplicates.items())[:5])
        result["message"] = "数量一致（注意重复广告语：%s，改名阶段需人工核对）" % dup_text
        result["duplicates"] = duplicates
    else:
        result["message"] = "数量一致，共 %d 条" % len(copies)
    return result
