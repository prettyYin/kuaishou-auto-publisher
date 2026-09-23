# -*- coding: utf-8 -*-
"""浏览器探测：不限定 Chrome，只要是 Chromium 内核就能被接管。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from . import config as cfgmod

# (显示名, [可能的 exe 路径], 默认用户数据目录)
CANDIDATES = [
    (
        "Google Chrome",
        [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        r"%LOCALAPPDATA%\Google\Chrome\User Data",
    ),
    (
        "Microsoft Edge",
        [
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        ],
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data",
    ),
    (
        "Brave",
        [
            r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data",
    ),
    (
        "360 极速浏览器",
        [
            r"%LOCALAPPDATA%\360ChromeX\Chrome\Application\360ChromeX.exe",
            r"%ProgramFiles(x86)%\360\360Chrome\Chrome\Application\360chrome.exe",
        ],
        r"%LOCALAPPDATA%\360ChromeX\Chrome\User Data",
    ),
    (
        "QQ 浏览器",
        [
            r"%ProgramFiles(x86)%\Tencent\QQBrowser\QQBrowser.exe",
            r"%ProgramFiles%\Tencent\QQBrowser\QQBrowser.exe",
        ],
        r"%LOCALAPPDATA%\Tencent\QQBrowser\User Data",
    ),
    (
        "搜狗高速浏览器",
        [
            r"%ProgramFiles(x86)%\SogouExplorer\SogouExplorer.exe",
            r"%ProgramFiles%\SogouExplorer\SogouExplorer.exe",
        ],
        r"%LOCALAPPDATA%\SogouExplorer\User Data",
    ),
    (
        "Vivaldi",
        [
            r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe",
            r"%ProgramFiles%\Vivaldi\Application\vivaldi.exe",
        ],
        r"%LOCALAPPDATA%\Vivaldi\User Data",
    ),
    (
        "Opera",
        [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
            r"%ProgramFiles%\Opera\opera.exe",
        ],
        r"%APPDATA%\Opera Software\Opera Stable",
    ),
]

MANUAL_LABEL = "其他浏览器（在配置文件里手填路径）"


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def detect_browsers() -> List[Dict[str, str]]:
    """返回本机可用的 Chromium 内核浏览器列表。"""
    found: List[Dict[str, str]] = []
    seen = set()
    for name, paths, user_data in CANDIDATES:
        for raw in paths:
            exe = _expand(raw)
            if exe.exists() and str(exe) not in seen:
                found.append(
                    {
                        "name": name,
                        "exe": str(exe),
                        "user_data_dir": str(_expand(user_data)),
                    }
                )
                seen.add(str(exe))
                break
    found.append({"name": MANUAL_LABEL, "exe": "", "user_data_dir": ""})
    return found


def browser_labels() -> List[str]:
    return [item["name"] for item in detect_browsers()]


def find_browser(cfg: Dict, account: Optional[Dict] = None) -> Dict[str, str]:
    """决定某个账号用哪个浏览器：账号设置 → 全局设置 → 自动探测。"""
    account = account or {}
    exe = cfgmod.expand_path(account.get("browser_exe", "") or "")
    user_data = cfgmod.expand_path(account.get("browser_source_user_data", "") or "")
    if exe and Path(exe).exists():
        return {"name": account.get("browser_name") or Path(exe).name, "exe": exe, "user_data_dir": user_data}
    global_exe = cfgmod.expand_path((cfg or {}).get("browser_exe", "") or "")
    if global_exe and Path(global_exe).exists():
        return {
            "name": Path(global_exe).name,
            "exe": global_exe,
            "user_data_dir": cfgmod.expand_path((cfg or {}).get("browser_user_data_dir", "") or ""),
        }
    for item in detect_browsers():
        if item["exe"]:
            return item
    raise FileNotFoundError(
        "没有找到可用的 Chromium 内核浏览器（Chrome / Edge 等）。\n"
        "请在「设置」里指定浏览器，或安装 Chrome / Edge 后重试。"
    )
