# -*- coding: utf-8 -*-
"""准备自动化专用的 Chrome 配置副本（保留登录态）。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config as cfgmod
from .browser import copy_profile, list_chrome_profiles


def _show_profiles(user_data_dir: str) -> list:
    profiles = list_chrome_profiles(user_data_dir)
    print("在 %s 里发现这些 Chrome 配置：" % user_data_dir)
    if not profiles:
        print("  （没读到，请确认路径是否正确、Chrome 是否装在这个用户下）")
    for index, (dir_name, display) in enumerate(profiles, start=1):
        print("  %d) %-12s %s" % (index, dir_name, display))
    return profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="为每个账号准备自动化专用的 Chrome 配置副本")
    parser.add_argument("--account", help="只处理指定账号名")
    parser.add_argument("--all", action="store_true", help="按配置文件里的映射直接复制，不逐个询问")
    parser.add_argument("--fresh", action="store_true", help="先清空已有的自动化副本再复制")
    args = parser.parse_args()

    cfg = cfgmod.load_config()
    accounts = cfg.get("accounts", [])
    if args.account:
        accounts = [acc for acc in accounts if (acc.get("name") or "") == args.account]
        if not accounts:
            print("没有找到账号：%s" % args.account)
            return 1
    for account in accounts:
        name = account.get("name") or "未命名账号"
        source_root = cfgmod.expand_path(account.get("browser_source_user_data") or "")
        current = account.get("browser_source_profile") or ""
        auto_dir = cfgmod.account_auto_dir(cfg, account)
        print("\n=== 账号：%s ===" % name)
        print("源配置目录：%s" % source_root)
        print("当前使用配置：%s" % current)
        print("自动化副本：%s" % auto_dir)
        if not args.all:
            profiles = _show_profiles(source_root)
            hint = "请输入要使用的配置编号（回车沿用 %s，输入 s 跳过该账号）：" % current
            answer = input(hint).strip()
            if answer.lower() == "s":
                print("已跳过 %s" % name)
                continue
            if answer.isdigit() and profiles:
                pick = int(answer)
                if 1 <= pick <= len(profiles):
                    current = profiles[pick - 1][0]
                    account["browser_source_profile"] = current
        if not Path(source_root).is_dir():
            print("× 源配置目录不存在，先跳过：%s" % source_root)
            continue
        print("正在复制（保留登录态，跳过缓存文件）…")
        try:
            copy_profile(source_root, current, auto_dir, fresh=args.fresh, logger=None)
        except Exception as exc:
            print("× 复制失败：%s" % exc)
            continue
        print("√ 完成：%s" % auto_dir)
        print("  下次脚本会用这个副本启动 Chrome，你原来的浏览器不受影响。")
    cfgmod.save_config(cfg)
    print("\n配置已保存：%s" % cfgmod.CONFIG_PATH)
    if not args.all and not args.account:
        print("提示：如果某个账号复制后打开发现没登录，在那个自动化窗口里扫码登录一次即可，之后会长期有效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
