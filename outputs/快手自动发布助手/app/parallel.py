# -*- coding: utf-8 -*-
"""账号级并行调度与安全预检。"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from . import config as cfgmod


def normalize_max_accounts(value: Any, default: int = 2, maximum: int = 5) -> int:
    try:
        number = int(float(str(value).strip()))
    except Exception:
        number = int(default)
    return max(1, min(int(maximum), number))


def _norm_path(value: Any) -> str:
    text = cfgmod.expand_path(str(value or ""))
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


def creator_auto_dir(cfg: Dict[str, Any], account: Dict[str, Any]) -> str:
    return _norm_path(cfgmod.account_auto_dir(cfg, account))


def jinniu_auto_dir(cfg: Dict[str, Any], account: Dict[str, Any]) -> str:
    explicit = account.get("jinniu_chrome_auto_dir")
    if explicit:
        return _norm_path(explicit)
    return creator_auto_dir(cfg, account)


def login_identity(cfg: Dict[str, Any], account: Dict[str, Any]) -> Tuple[str, str]:
    profile = str(account.get("browser_source_profile") or "").strip().lower()
    if not profile:
        return "", ""
    root = account.get("browser_source_user_data") or ""
    if not root:
        try:
            from .browsers import find_browser

            root = (find_browser(cfg, account) or {}).get("user_data_dir") or ""
        except Exception:
            root = ""
    return _norm_path(root), profile


def preflight_parallel(cfg: Dict[str, Any], accounts: Sequence[Dict[str, Any]]) -> List[str]:
    """返回阻止并行启动的问题列表；空列表表示可以并行。"""
    problems: List[str] = []
    seen_dirs: Dict[str, str] = {}
    seen_jinniu_dirs: Dict[str, str] = {}
    seen_ports: Dict[int, str] = {}
    seen_logins: Dict[Tuple[str, str], str] = {}
    seen_jinniu_ids: Dict[str, str] = {}

    for account in accounts:
        name = str(account.get("name") or "未命名账号")

        auto_dir = creator_auto_dir(cfg, account)
        if auto_dir:
            if auto_dir in seen_dirs and seen_dirs[auto_dir] != name:
                problems.append("账号「%s」和「%s」使用了同一个自动化浏览器目录" % (seen_dirs[auto_dir], name))
            else:
                seen_dirs[auto_dir] = name

        jdir = jinniu_auto_dir(cfg, account)
        if jdir:
            if jdir in seen_jinniu_dirs and seen_jinniu_dirs[jdir] != name:
                problems.append("账号「%s」和「%s」使用了同一个金牛自动化目录" % (seen_jinniu_dirs[jdir], name))
            else:
                seen_jinniu_dirs[jdir] = name

        try:
            port = int(account.get("debug_port") or 0)
        except Exception:
            port = 0
        if port:
            if port in seen_ports and seen_ports[port] != name:
                problems.append("账号「%s」和「%s」使用了同一个调试端口 %d" % (seen_ports[port], name, port))
            else:
                seen_ports[port] = name

        identity = login_identity(cfg, account)
        if identity[1]:
            if identity in seen_logins and seen_logins[identity] != name:
                problems.append("账号「%s」和「%s」复用了同一份创作者平台登录配置" % (seen_logins[identity], name))
            else:
                seen_logins[identity] = name

        jinniu_id = str(account.get("jinniu_account_id") or "").strip()
        if jinniu_id:
            if jinniu_id in seen_jinniu_ids and seen_jinniu_ids[jinniu_id] != name:
                problems.append("账号「%s」和「%s」使用了同一个金牛账户ID" % (seen_jinniu_ids[jinniu_id], name))
            else:
                seen_jinniu_ids[jinniu_id] = name

    return problems


def run_parallel_jobs(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    max_workers: int = 2,
) -> Tuple[List[Any], List[Tuple[Any, Exception]]]:
    """并行执行项目；返回 (成功结果, [(项目, 异常)])。单个失败不会取消其他项目。"""
    values = list(items)
    results: List[Any] = []
    errors: List[Tuple[Any, Exception]] = []
    workers = max(int(max_workers), 1)
    if workers == 1:
        for item in values:
            try:
                results.append(worker(item))
            except Exception as exc:
                errors.append((item, exc))
        return results, errors
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, item): item for item in values}
        for future in as_completed(futures):
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append((item, exc))
    return results, errors
