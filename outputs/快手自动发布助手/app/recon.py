# -*- coding: utf-8 -*-
"""页面勘查：打开真实页面，抓取结构、截图和可交互元素清单。

用法（双击「运行勘查.bat」，或命令行）：
    python -X utf8 -m app.recon --account 账号A
交互：在打开的 Chrome 里点到要勘查的页面，回到命令行按回车抓取一次；
      u 跳转网址；q 结束。
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

from . import config as cfgmod
from .browser import ChromeSession, attached_page, copy_profile, pick_free_port
from .snapshot import capture, safe_url


def main() -> int:
    parser = argparse.ArgumentParser(description="页面勘查")
    parser.add_argument("--account", help="要勘查的账号名（默认第一个启用的账号）")
    parser.add_argument("--url", help="启动时直接打开的网址")
    parser.add_argument("--tag", default="勘查", help="快照文件名标签")
    args = parser.parse_args()

    cfg = cfgmod.load_config()
    accounts = cfg.get("accounts", [])
    if args.account:
        accounts = [acc for acc in accounts if (acc.get("name") or "") == args.account]
    else:
        enabled = [acc for acc in accounts if acc.get("enabled")]
        accounts = enabled[:1] or accounts[:1]
    if not accounts:
        print("配置里没有账号，请先在 config/config.json 里填账号信息。")
        return 1
    account = accounts[0]
    name = account.get("name") or "未命名账号"
    from .browsers import find_browser

    chrome = find_browser(cfg, account)["exe"]
    auto_dir = cfgmod.account_auto_dir(cfg, account)
    if not (auto_dir / "Default").is_dir():
        source_root = cfgmod.expand_path(account.get("browser_source_user_data") or "")
        source_profile = account.get("browser_source_profile") or ""
        if source_profile:
            print("首次使用：正在为「%s」复制浏览器配置副本…" % name)
            print("（如果这个浏览器配置的窗口正开着，建议先关掉再复制）")
            copy_profile(source_root, source_profile, auto_dir, fresh=False)
        else:
            auto_dir.mkdir(parents=True, exist_ok=True)
            print("首次使用：将为「%s」打开一个干净的浏览器窗口，请在窗口里扫码登录一次。" % name)
    port = pick_free_port(int(account.get("debug_port", 9222)))
    session = ChromeSession(chrome, port, auto_dir)
    urls = []
    if args.url:
        urls.append(args.url)
    elif cfg.get("creator", {}).get("publish_url"):
        urls.append(cfg["creator"]["publish_url"])
    endpoint = session.start(urls)
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser, context, page = attached_page(playwright, endpoint)
    folder = cfgmod.RECON_DIR / ("%s_%s" % (name, datetime.now().strftime("%Y%m%d_%H%M%S")))
    print("")
    print("已打开自动化 Chrome（账号：%s）。" % name)
    print("请在这个窗口里点到要勘查的页面（发布作品页 / 金牛视频库 / 批量改名弹窗等）。")
    print("每按一次回车抓取一次；u 跳转网址；q 结束。")
    print("")
    count = 0
    while True:
        answer = input("回车=抓取当前页面 / u=跳转 / q=退出：").strip().lower()
        if answer == "q":
            break
        if answer == "u":
            target = input("请输入要打开的网址：").strip()
            if target:
                page.goto(target, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(2500)
            continue
        count += 1
        info = capture(page, folder, "%s_%02d" % (args.tag, count))
        print("  已抓取：%s" % safe_url(page))
        print("  可交互元素：%s 个" % info.get("element_count", "?"))
        print("  保存到：%s" % folder)
    print("")
    print("勘查结束，请把整个目录发给助手分析：")
    print("  %s" % folder)
    try:
        os.startfile(str(folder))
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    playwright.stop()
    session.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
