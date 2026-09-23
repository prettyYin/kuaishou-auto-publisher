# -*- coding: utf-8 -*-
"""配置与路径管理。"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

# 工具根目录（app 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"
SELECTORS_PATH = CONFIG_DIR / "selectors.json"
LOG_DIR = BASE_DIR / "logs"
SHOT_DIR = LOG_DIR / "shots"
RECON_DIR = LOG_DIR / "recon"
RUN_DIR = BASE_DIR / "runs"

ACCOUNT_PLACEHOLDER = {
    "name": "账号A",
    "enabled": False,
    "video_dir": "",
    # 浏览器：留空表示自动使用本机检测到的 Chromium 内核浏览器（Chrome / Edge 等）
    "browser_name": "",
    "browser_exe": "",
    # 复用已有登录：填用户数据目录 + 配置名；两者留空 = 新建干净窗口、首次扫码登录
    "browser_source_user_data": "",
    "browser_source_profile": "",
    "browser_auto_dir": "",
    "debug_port": 9222,
    "extra_actions": [],
    "notes": "",
    "jinniu_chrome_source_profile": "",
    "jinniu_chrome_auto_dir": "",
    # 这个账号自己的磁力金牛视频库地址（首次自动识别后自动写入）
    "jinniu_video_library_url": "",
    # 这个账号在磁力金牛里的账户 ID（必填，用于拼出正确的素材库地址）
    "jinniu_account_id": "",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 2,
    # 自动化专用浏览器数据目录的存放位置（"准备浏览器配置"时用）
    "automation_data_dir": r"%LOCALAPPDATA%\KuaishouAuto",
    "browser_exe": "",
    "browser_user_data_dir": "",
    "creator": {
        # 创作者服务平台的上传/发布页地址；留空则脚本会提示你手动打开一次
        "publish_url": "",
        # 发布完成后停留页（用于核对是否发布成功），可留空
        "works_url": "",
        "upload_timeout_seconds": 1800,
        # 上传/转码看起来完成后，再稳定观察多少秒才认为真的好了
        "upload_settle_seconds": 10,
        "publish_confirm_timeout_seconds": 600,
        "post_publish_wait_seconds": 15,
        "inter_account_wait_seconds": 30,
        "daily_total_limit": 120,
        "manual_rescue": True,
        # 上传页出现「上次未发布的草稿」提示时：dismiss=直接放弃草稿，ask=弹窗询问
        "on_resume_dialog": "dismiss",
        # 发布前取消勾选「允许下载此作品」
        "uncheck_download": True,
        # 作者声明：与创作者平台保持一致的候选项；空字符串表示不设置
        "author_declaration_options": [
            "内容为AI生成",
            "演绎情节，仅供娱乐",
            "个人观点，仅供参考",
            "素材来源于网络",
        ],
        # 作者声明失败后自动重试次数（初次之外再重试几次）
        "author_statement_retries": 2,
        # 不设置作者声明时，发布前把页面上残留的选择清掉
        "clear_author_statement_when_empty": True,
        # 定时发布的安全边界（实施时若平台规则不同，改这里即可）
        "schedule_min_lead_minutes": 60,
        "schedule_max_days": 14,
        # 只要本账号有定时发布，就不自动执行金牛改名
        "auto_rename_when_scheduled": False,
        # 账号级并行执行：默认同时 2 个账号，0 表示同时启动不额外错开
        "parallel_max_accounts": 2,
        "parallel_start_interval_seconds": 0,
        "parallel_risk_acked": False,
        "extra_actions": [],
    },
    "jinniu": {
        # 磁力金牛视频库/素材库地址；留空则脚本会提示你手动打开一次
        "video_library_url": "",
        # 查询前先确认这个筛选字段（素材名称 / 素材ID / 创建时间）
        "filter_field": "素材名称",
        # 查到条数对不上时：ask=停下询问，retry=自动等待重查，skip=只改对得上的
        "on_mismatch": "ask",
        # 选「等一会儿再查一次」时等待多少秒
        "retry_wait_seconds": 60,
        # 改名方式：by_title=按广告语搜索素材再逐条改名；by_time_reverse=按上传时间倒序对应；auto=先试前者
        "rename_mode": "auto",
        # 素材列表的排序方向：newest_first = 最新上传的排在列表最上面
        "list_order": "newest_first",
        # 改名前的核对表：false = 直接执行，不再弹窗确认
        "confirm_mapping": False,
        # 发布后等待多少秒让素材同步到金牛素材库
        "sync_wait_seconds": 60,
        # 时长兜底校验：auto=多条一起改名时才逐条核对时长，on=总是核对，off=不核对
        "duration_check": "auto",
        # 完整广告语查不全时，改用前多少个字再查一次（平台按分词匹配，太短会查不到）
        "fallback_keyword_chars": 12,
        # 允许用"截断的广告语"兜底查询（默认关闭：小组共用同样的广告语，截断容易查到同事的素材）
        "allow_short_keyword": False,
        # 时长比对的容差（秒）：越小越严格，避免时长接近的两条互相错配
        "duration_tolerance_seconds": 1,
        "settle_wait_seconds": 5,
        "material_row_limit": 60,
    },
    "accounts": [],
}


_ACCOUNT_ID_IN_URL = re.compile(r"([?&])__accountId__=[^&]*")


def strip_account_id(url: str) -> str:
    """去掉地址里的 __accountId__（公共地址不该写死某个账号）。"""
    if not url:
        return ""
    cleaned = _ACCOUNT_ID_IN_URL.sub(lambda match: match.group(1), url)
    cleaned = cleaned.replace("?&", "?").replace("??", "?").rstrip("?&")
    return cleaned


def build_library_url(cfg: Dict[str, Any], account: Dict[str, Any]) -> str:
    """按账号拼出金牛素材库地址：公共地址 + 该账号自己的 accountId。"""
    base = (account.get("jinniu_video_library_url") or "").strip() or (
        (cfg.get("jinniu") or {}).get("video_library_url") or ""
    ).strip()
    account_id = str(account.get("jinniu_account_id") or "").strip()
    if not base:
        return ""
    if not account_id:
        return base
    if "__accountId__=" in base:
        url = _ACCOUNT_ID_IN_URL.sub(
            lambda match: "%s__accountId__=%s" % (match.group(1), account_id), base
        )
        # 防御：万一地址里出现多个 __accountId__，只保留一个（避免 ?__accountId__=&__accountId__=xxx）
        if url.count("__accountId__") > 1:
            url = "%s?__accountId__=%s" % (url.split("?")[0], account_id)
        return url
    separator = "&" if "?" in base else "?"
    return "%s%s__accountId__=%s" % (base, separator, account_id)


def expand_path(value: str) -> str:
    """展开 %VAR% 与 ~，返回绝对路径字符串。"""
    if not value:
        return ""
    return os.path.expandvars(os.path.expanduser(str(value)))


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, val in override.items():
            merged[key] = _deep_merge(base.get(key), val)
        return merged
    return copy.deepcopy(override)


def default_account(index: int) -> Dict[str, Any]:
    acc = copy.deepcopy(ACCOUNT_PLACEHOLDER)
    acc["name"] = "账号%s" % chr(ord("A") + index) if index < 26 else "账号%d" % (index + 1)
    acc["debug_port"] = 9222 + index
    return acc


LEGACY_BROWSER_KEYS = {
    "chrome_exe": "browser_exe",
    "chrome_source_user_data": "browser_source_user_data",
    "chrome_source_profile": "browser_source_profile",
    "chrome_auto_dir": "browser_auto_dir",
}


def migrate_account(account: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧版配置里的 chrome_* 字段。"""
    for old_key, new_key in LEGACY_BROWSER_KEYS.items():
        if old_key in account:
            if not account.get(new_key):
                account[new_key] = account[old_key]
            account.pop(old_key, None)
    return account


def load_config(path: Path | str = CONFIG_PATH) -> Dict[str, Any]:
    path = Path(path)
    raw: Dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    cfg = _deep_merge(DEFAULT_CONFIG, raw)
    # 平台规则是未来 1 小时到 14 天内；旧配置里短暂的 1/5 分钟默认值自动迁移回 60 分钟。
    try:
        creator_cfg = cfg.setdefault("creator", {})
        if int(creator_cfg.get("schedule_min_lead_minutes", 0) or 0) in (1, 5):
            creator_cfg["schedule_min_lead_minutes"] = 60
        if int(creator_cfg.get("schedule_max_days", 0) or 0) == 7:
            creator_cfg["schedule_max_days"] = 14
    except Exception:
        pass
    legacy_exe = raw.get("chrome_exe") if isinstance(raw, dict) else None
    if legacy_exe and not cfg.get("browser_exe"):
        cfg["browser_exe"] = legacy_exe
    accounts: List[Dict[str, Any]] = cfg.get("accounts") or []
    cfg["accounts"] = [migrate_account(item) for item in accounts]
    return cfg


def save_config(cfg: Dict[str, Any], path: Path | str = CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)


def enabled_accounts(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [acc for acc in cfg.get("accounts", []) if acc.get("enabled")]


def account_auto_dir(cfg: Dict[str, Any], account: Dict[str, Any]) -> Path:
    """账号的自动化浏览器数据目录。"""
    explicit = expand_path(account.get("browser_auto_dir", ""))
    if explicit:
        return Path(explicit)
    root = Path(expand_path(cfg.get("automation_data_dir", "")))
    safe = "".join(ch if ch not in r'\/:*?"<>|' else "_" for ch in (account.get("name") or "account"))
    return root / safe


def ensure_dirs() -> None:
    for folder in (CONFIG_DIR, LOG_DIR, SHOT_DIR, RECON_DIR, RUN_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def find_chrome(cfg: Dict[str, Any]) -> str:
    """兼容旧接口：返回本机可用的浏览器可执行文件路径。"""
    from .browsers import find_browser

    return find_browser(cfg)["exe"]
