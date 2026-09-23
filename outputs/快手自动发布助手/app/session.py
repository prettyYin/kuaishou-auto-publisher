# -*- coding: utf-8 -*-
"""按账号打开自动化浏览器窗口（运行、登录检查、页面勘查共用）。

两种登录方式：
  1) 复用已有浏览器配置：复制一份配置副本（保留登录态），不影响日常浏览；
  2) 新建干净窗口：不动任何已有配置，第一次在自动化窗口里扫码登录一次即可。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional

from . import config as cfgmod
from .browser import ChromeSession, attached_page, cdp_endpoint, copy_profile, pick_free_port, set_files_via_cdp
from .browsers import find_browser
from .snapshot import capture, safe_url

MODES = ("setup", "creator", "jinniu")


class AccountBrowser:
    """为某个账号打开一个独立的自动化浏览器窗口。"""

    def __init__(
        self,
        cfg: Dict[str, Any],
        account: Dict[str, Any],
        mode: str = "setup",
        logger=None,
        progress: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.cfg = cfg
        self.account = account
        self.mode = mode if mode in MODES else "setup"
        self.logger = logger
        self.progress = progress or (lambda text: None)
        self.should_stop = should_stop or (lambda: False)
        self.chrome: Optional[ChromeSession] = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.auto_dir: Optional[Path] = None
        self.browser_info: Dict[str, str] = {}
        self.reuse_login = False
        self.owner_thread = threading.get_ident()
        self.port = 0

    # ---------- 路径与配置 ----------
    def resolve_target(self):
        """返回 (浏览器信息, 源用户数据目录, 源配置名, 自动化数据目录)。"""
        info = find_browser(self.cfg, self.account)
        source_root = cfgmod.expand_path(self.account.get("browser_source_user_data") or "")
        if not source_root:
            source_root = info.get("user_data_dir") or ""
        profile = (self.account.get("browser_source_profile") or "").strip()
        auto_dir = cfgmod.account_auto_dir(self.cfg, self.account)
        if self.mode == "jinniu":
            if self.account.get("jinniu_chrome_source_profile"):
                profile = self.account["jinniu_chrome_source_profile"]
            if self.account.get("jinniu_chrome_auto_dir"):
                auto_dir = Path(cfgmod.expand_path(self.account["jinniu_chrome_auto_dir"]))
        return info, source_root, profile, auto_dir

    def ensure_profile_copy(self, fresh: bool = False) -> Path:
        info, source_root, profile, auto_dir = self.resolve_target()
        self.browser_info = info
        name = self.account.get("name") or "账号"
        if not profile:
            self.reuse_login = False
            auto_dir.mkdir(parents=True, exist_ok=True)
            self.progress("「%s」将使用新建的干净浏览器窗口（第一次需要扫码登录一次）" % name)
            self.auto_dir = auto_dir
            return auto_dir
        self.reuse_login = True
        if fresh or not (auto_dir / "Default").is_dir():
            self.progress("正在为「%s」复制浏览器配置（只复制登录相关文件，通常几秒钟）…" % name)
            copy_profile(
                source_root,
                profile,
                auto_dir,
                fresh=fresh,
                logger=self.logger,
                should_stop=self.should_stop,
                mode=(self.cfg.get("browser_copy_mode") or "lean"),
                progress=self.progress,
            )
            self.progress("浏览器配置已就绪：%s" % auto_dir)
        self.auto_dir = auto_dir
        return auto_dir

    def start_urls(self, extra_urls: Optional[List[str]] = None) -> List[str]:
        urls: List[str] = []
        if self.mode == "creator":
            url = (self.cfg.get("creator") or {}).get("publish_url")
            if url:
                urls.append(url)
        elif self.mode == "jinniu":
            url = cfgmod.build_library_url(self.cfg, self.account)
            if url:
                urls.append(url)
        urls.extend(extra_urls or [])
        return urls

    # ---------- 生命周期 ----------
    def start(self, fresh: bool = False, extra_urls: Optional[List[str]] = None) -> "AccountBrowser":
        auto_dir = self.ensure_profile_copy(fresh=fresh)
        exe = self.browser_info.get("exe") or cfgmod.find_chrome(self.cfg)
        port = pick_free_port(int(self.account.get("debug_port", 9222)), self.logger)
        self.chrome = ChromeSession(exe, port, auto_dir, self.logger)
        self.port = port
        urls = self.start_urls(extra_urls)
        endpoint = self.chrome.start(urls, should_stop=self.should_stop, progress=self.progress)
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        self.browser, self.context, self.page = attached_page(self.playwright, endpoint, urls[0] if urls else "")
        # 复用了之前开着的窗口时，可能还停在别的页面（例如上一轮的金牛页面），这里切回去
        if urls and self.page is not None:
            expected_host = urls[0].split("//")[-1].split("/")[0]
            current = self.page.url or ""
            if expected_host and expected_host not in current:
                self.progress("浏览器还停在别的页面，正在切换到 %s …" % expected_host)
                self.logger.info("当前页面 %s 不是预期的 %s，正在跳转", current or "空白页", expected_host)
                try:
                    self.page.goto(urls[0], wait_until="domcontentloaded", timeout=90000)
                    self.page.wait_for_timeout(1800)
                except Exception as exc:
                    self.logger.warning("切换页面失败：%s", exc)
        try:
            self.page.wait_for_timeout(800)
            self.page.bring_to_front()
        except Exception:
            pass
        return self

    def alive(self) -> bool:
        """只检查调试端口（线程安全，不碰 Playwright 对象）。"""
        if not self.port:
            return False
        if cdp_endpoint(self.port) is None:
            return False
        return True

    def capture(self, tag: str, subfolder: Optional[str] = None) -> Dict[str, Any]:
        if not self.alive():
            raise RuntimeError("浏览器窗口已经关闭，请先打开浏览器再抓取")
        safe = "".join(ch if ch not in r'\/:*?"<>|' else "_" for ch in (self.account.get("name") or "账号"))
        folder = cfgmod.RECON_DIR / (subfolder or ("%s_%s" % (safe, datetime.now().strftime("%Y%m%d_%H%M%S"))))
        # Playwright 对象只能被创建它的线程使用：这里新开一个连接来抓取
        from playwright.sync_api import sync_playwright

        endpoint = cdp_endpoint(self.port) or ("http://127.0.0.1:%d" % self.port)
        playwright = sync_playwright().start()
        browser = None
        try:
            browser = playwright.chromium.connect_over_cdp(endpoint)
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()
            pages = [pg for pg in context.pages if (pg.url or "") != "about:blank"]
            page = pages[0] if pages else (context.pages[0] if context.pages else context.new_page())
            return capture(page, folder, tag, logger=self.logger)
        finally:
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                playwright.stop()
            except Exception:
                pass

    def current_url(self) -> str:
        return safe_url(self.page) if self.page is not None else ""

    def goto(self, url: str) -> None:
        if self.page is None:
            raise RuntimeError("浏览器还没启动")
        self.page.goto(url, wait_until="domcontentloaded", timeout=90000)
        self.page.wait_for_timeout(1500)

    def close(self) -> None:
        same_thread = threading.get_ident() == self.owner_thread
        try:
            if same_thread and self.browser is not None:
                self.browser.close()
        except Exception:
            pass
        try:
            if same_thread and self.playwright is not None:
                self.playwright.stop()
        except Exception:
            pass
        try:
            if self.chrome is not None:
                self.chrome.stop()
        except Exception:
            pass
        self.page = None
        self.browser = None
        self.playwright = None
        self.chrome = None

    def __enter__(self) -> "AccountBrowser":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.close()
