# -*- coding: utf-8 -*-
"""浏览器与登录方式的下拉选项（设置页、引导向导共用）。"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import config as cfgmod
from .browser import list_chrome_profiles
from .browsers import detect_browsers

NEW_LOGIN_LABEL = "新建：首次扫码登录（推荐）"


def browser_list() -> List[Dict[str, str]]:
    return detect_browsers()


def browser_by_label() -> Dict[str, Dict[str, str]]:
    return {item["name"]: item for item in browser_list()}


def browser_labels() -> List[str]:
    return [item["name"] for item in browser_list()]


def default_browser_label() -> str:
    for item in browser_list():
        if item.get("exe"):
            return item["name"]
    return browser_labels()[0]


def login_options(browser_label: str, current_profile: str = "", browsers: Optional[Dict] = None) -> List[str]:
    """返回该浏览器下可选的登录方式：新建（扫码）或复用某个已有配置。"""
    info = (browsers or browser_by_label()).get(browser_label) or {}
    options = [NEW_LOGIN_LABEL]
    user_data = info.get("user_data_dir") or ""
    if user_data:
        for dir_name, display in list_chrome_profiles(cfgmod.expand_path(user_data)):
            options.append("复用：%s（%s）" % (display, dir_name))
    if current_profile and not any(("（%s）" % current_profile) in item for item in options):
        options.append("复用：%s（%s）" % (current_profile, current_profile))
    return options


def parse_login(value: str) -> str:
    """从下拉选项里取出配置目录名；返回空字符串表示"新建窗口扫码登录"。"""
    value = (value or "").strip()
    if value.startswith("复用：") and value.endswith("）") and "（" in value:
        return value[value.rindex("（") + 1 : -1]
    return ""


def login_label(profile: str) -> str:
    return ("复用：%s（%s）" % (profile, profile)) if profile else NEW_LOGIN_LABEL


def apply_to_account(account: Dict, browser_label: str, login_value: str, browsers: Optional[Dict] = None) -> Dict:
    """把界面上的选择写回账号配置。"""
    info = (browsers or browser_by_label()).get(browser_label) or {}
    account["browser_name"] = browser_label
    account["browser_exe"] = info.get("exe") or ""
    profile = parse_login(login_value)
    account["browser_source_profile"] = profile
    if profile:
        account["browser_source_user_data"] = info.get("user_data_dir") or account.get("browser_source_user_data") or ""
    else:
        account["browser_source_user_data"] = ""
    return account
