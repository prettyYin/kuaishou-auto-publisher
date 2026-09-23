# -*- coding: utf-8 -*-
"""设置页签：账号数量、浏览器、平台地址、运行节奏都能在界面上改。"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from . import config as cfgmod
from .browsers import detect_browsers
from .loginconfig import NEW_LOGIN_LABEL, apply_to_account, login_options, parse_login

TITLE_FONT = ("Microsoft YaHei UI", 11, "bold")
LABEL_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)

LIST_ORDER_LABELS = {
    "最新上传的排在最上面": "newest_first",
    "最早上传的排在最上面": "oldest_first",
}
RENAME_MODE_LABELS = {
    "先按广告语搜索素材再改名（推荐）": "by_title",
    "按上传时间倒序批量改名": "by_time_reverse",
    "自动：先试搜索，失败再按时间": "auto",
}
def build_settings_tab(parent, app) -> "SettingsTab":
    return SettingsTab(parent, app)


class SettingsTab:
    def __init__(self, parent: tk.Widget, app) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.account_rows: List[Dict[str, Any]] = []
        self.busy_var = tk.StringVar(value="")
        self.url_var = tk.StringVar(value="")
        self.browsers = detect_browsers()
        self.browser_by_label = {item["name"]: item for item in self.browsers}

        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        head = ttk.Frame(inner)
        head.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(head, text="设置", font=TITLE_FONT).pack(side="left")
        ttk.Button(head, text="保存设置", command=self.save_to_config).pack(side="right", padx=4)
        ttk.Button(head, text="开始引导设置", command=app.open_wizard).pack(side="right", padx=4)
        ttk.Label(
            inner,
            text="第一次配好以后，每天直接回「今天要发的」页签操作即可。账号数量可以随时加减。",
            font=SMALL_FONT,
            foreground="#666666",
        ).pack(anchor="w", padx=12)

        self._build_platform(inner)
        self._build_accounts(inner)
        self._build_browser(inner)
        self._build_tools(inner)
        self.load_from_config()

    # ---------- 平台与节奏 ----------
    def _build_platform(self, parent: tk.Widget) -> None:
        box = ttk.LabelFrame(parent, text=" 平台地址 ")
        box.pack(fill="x", padx=12, pady=6)
        self.publish_url = tk.StringVar()
        self.works_url = tk.StringVar()
        self.jinniu_url = tk.StringVar()
        self.list_order = tk.StringVar(value="最新上传的排在最上面")
        self.rename_mode = tk.StringVar(value="先按广告语搜索素材再改名（推荐）")
        for label, var, hint in (
            ("创作者平台发布页", self.publish_url, "打开「发布作品」页面后复制地址栏"),
            ("作品管理页（可留空）", self.works_url, ""),
            ("磁力金牛视频库", self.jinniu_url, "只填公共地址（不要带 __accountId__），每个账号的账户 ID 在下面各自填写"),
        ):
            row = ttk.Frame(box)
            row.pack(fill="x", padx=8, pady=4)
            ttk.Label(row, text=label, font=LABEL_FONT, width=17).pack(side="left")
            ttk.Entry(row, textvariable=var, font=SMALL_FONT).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="打开验证", width=9, command=lambda v=var: self.open_url(v.get())).pack(side="left", padx=4)
            if hint:
                ttk.Label(row, text=hint, font=SMALL_FONT, foreground="#888888").pack(side="left", padx=4)

        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Label(row, text="金牛改名方式", font=LABEL_FONT, width=17).pack(side="left")
        ttk.Combobox(row, textvariable=self.rename_mode, values=list(RENAME_MODE_LABELS.keys()), state="readonly", width=30).pack(side="left")
        ttk.Label(row, text="列表顺序", font=LABEL_FONT).pack(side="left", padx=(16, 4))
        ttk.Combobox(row, textvariable=self.list_order, values=list(LIST_ORDER_LABELS.keys()), state="readonly", width=22).pack(side="left")
        ttk.Label(
            row,
            text="（倒序方式下：金牛最新在最上面，所以列表第 1 条对应文件夹里最后一条视频）",
            font=SMALL_FONT,
            foreground="#888888",
        ).pack(side="left", padx=6)

        pace = ttk.Frame(box)
        pace.pack(fill="x", padx=8, pady=(0, 8))
        self.wait_after = tk.StringVar(value="10")
        self.wait_account = tk.StringVar(value="30")
        self.daily_limit = tk.StringVar(value="120")
        for label, var, unit in (
            ("每条发布后等待", self.wait_after, "秒"),
            ("账号之间休息", self.wait_account, "秒"),
            ("当日条数上限", self.daily_limit, "条"),
        ):
            cell = ttk.Frame(pace)
            cell.pack(side="left", padx=(0, 20))
            ttk.Label(cell, text=label, font=LABEL_FONT).pack(anchor="w")
            line = ttk.Frame(cell)
            line.pack(anchor="w")
            ttk.Entry(line, textvariable=var, width=6, font=LABEL_FONT).pack(side="left")
            ttk.Label(line, text=unit, font=SMALL_FONT).pack(side="left", padx=2)

    # ---------- 账号 ----------
    def _build_accounts(self, parent: tk.Widget) -> None:
        self.accounts_box = ttk.LabelFrame(parent, text=" 账号（可以随时加/减） ")
        self.accounts_box.pack(fill="x", padx=12, pady=6)
        ttk.Label(
            self.accounts_box,
            text="每个账号可以选不同的浏览器。选「新建：首次扫码登录」最省事：不动你现有的浏览器，"
            "第一次在自动化窗口里扫码登录一次就行。\n如果想直接用已经登录好的配置，就选「复用：…」。",
            font=SMALL_FONT,
            foreground="#666666",
            justify="left",
        ).pack(anchor="w", padx=8, pady=(6, 2))
        self.rows_holder = ttk.Frame(self.accounts_box)
        self.rows_holder.pack(fill="x")
        bar = ttk.Frame(self.accounts_box)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="＋ 添加账号", command=self.add_account_from_settings).pack(side="left")
        ttk.Label(
            bar,
            text="（加完别忘了点右上角「保存设置」）",
            font=SMALL_FONT,
            foreground="#888888",
        ).pack(side="left", padx=8)

    def _browser_labels(self) -> List[str]:
        return [item["name"] for item in self.browsers]

    def _login_options(self, browser_label: str, current_profile: str = "") -> List[str]:
        return login_options(browser_label, current_profile, self.browser_by_label)

    def _make_account_row(self, account: Dict[str, Any]) -> Dict[str, Any]:
        outer = ttk.Frame(self.rows_holder)
        outer.pack(fill="x", padx=8, pady=3)
        row = ttk.Frame(outer)
        row.pack(fill="x")
        name = tk.StringVar(value=account.get("name") or "")
        browser_label = account.get("browser_name") or ""
        if browser_label not in self.browser_by_label:
            browser_label = next((item["name"] for item in self.browsers if item.get("exe")), self._browser_labels()[0])
        browser_var = tk.StringVar(value=browser_label)
        profile = account.get("browser_source_profile") or ""
        options = self._login_options(browser_label, profile)
        current = next((item for item in options if profile and item.endswith("（%s）" % profile)), NEW_LOGIN_LABEL)
        login_var = tk.StringVar(value=current)
        login_combo = ttk.Combobox(row, textvariable=login_var, values=options, state="readonly", width=34)
        browser_combo = ttk.Combobox(row, textvariable=browser_var, values=self._browser_labels(), state="readonly", width=16)

        def refresh_login(*_args) -> None:
            login_combo.configure(values=self._login_options(browser_var.get()))
            if login_var.get() not in login_combo.cget("values"):
                login_var.set(NEW_LOGIN_LABEL)

        browser_combo.bind("<<ComboboxSelected>>", refresh_login)
        ttk.Label(row, text="账号名", font=LABEL_FONT).pack(side="left", padx=(8, 2))
        ttk.Entry(row, textvariable=name, width=14, font=LABEL_FONT).pack(side="left")
        ttk.Label(row, text="浏览器", font=LABEL_FONT).pack(side="left", padx=(8, 2))
        browser_combo.pack(side="left")
        ttk.Label(row, text="登录方式", font=LABEL_FONT).pack(side="left", padx=(8, 2))
        login_combo.pack(side="left")
        ttk.Label(row, text="金牛账户ID（改名必填）", font=LABEL_FONT).pack(side="left", padx=(8, 2))
        account_id = tk.StringVar(value=str(account.get("jinniu_account_id") or ""))
        ttk.Entry(row, textvariable=account_id, width=13, font=SMALL_FONT).pack(side="left")
        row_data = {
            "frame": outer,
            "name": name,
            "account_id": account_id,
            "browser": browser_var,
            "login": login_var,
            "login_combo": login_combo,
        }
        ttk.Button(row, text="删除", width=6, command=lambda: self.delete_account_row(row_data)).pack(side="left", padx=2)
        ttk.Label(
            outer,
            text="当天是否运行、用哪个素材文件夹，请在「今天要发的」账号卡片上设置。",
            font=SMALL_FONT,
            foreground="#888888",
        ).pack(anchor="w", padx=8, pady=(0, 2))
        return row_data

    def delete_account_row(self, row_data: Dict[str, Any]) -> None:
        index = next((i for i, item in enumerate(self.account_rows) if item is row_data), None)
        if index is None:
            return
        name = row_data["name"].get().strip() or ("账号 %d" % (index + 1))
        if not messagebox.askyesno(
            "删除账号",
            "确定要删除「%s」吗？\n（只删除工具里的设置，不会动你的视频文件和账号）" % name,
            parent=self.app.root,
        ):
            return
        self.save_to_config(rebuild=False)
        accounts = self.app.cfg.setdefault("accounts", [])
        if index < len(accounts):
            accounts.pop(index)
        self.app.save_config()
        self.app.append_log("已删除账号：%s" % name)
        self.app.reload_from_config()
        self.app.set_status("已删除账号：%s" % name)

    def rebuild_account_rows(self) -> None:
        for widget in self.rows_holder.winfo_children():
            widget.destroy()
        self.account_rows = []
        accounts = self.app.cfg.get("accounts", [])
        if not accounts:
            ttk.Label(self.rows_holder, text="还没有账号，点下面的「＋ 添加账号」。", font=LABEL_FONT, foreground="#888888").pack(
                anchor="w", padx=8, pady=6
            )
        for account in accounts:
            self.account_rows.append(self._make_account_row(account))

    def add_account_from_settings(self) -> None:
        self.save_to_config(rebuild=False)
        accounts = self.app.cfg.setdefault("accounts", [])
        accounts.append(cfgmod.default_account(len(accounts)))
        self.app.save_config()
        self.app.reload_from_config()

    # ---------- 浏览器窗口 ----------
    def _build_browser(self, parent: tk.Widget) -> None:
        box = ttk.LabelFrame(parent, text=" 浏览器窗口 ")
        box.pack(fill="x", padx=12, pady=6)
        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(row, text="对哪个账号操作", font=LABEL_FONT).pack(side="left")
        self.target_account = tk.StringVar()
        self.account_picker = ttk.Combobox(row, textvariable=self.target_account, state="readonly", width=22)
        self.account_picker.pack(side="left", padx=6)
        ttk.Label(row, text="打开", font=LABEL_FONT).pack(side="left", padx=(10, 4))
        self.page_picker = tk.StringVar(value="创作者平台发布页")
        ttk.Combobox(
            row,
            textvariable=self.page_picker,
            values=["创作者平台发布页", "磁力金牛视频库", "空白页"],
            state="readonly",
            width=16,
        ).pack(side="left")
        self.browser_buttons = []
        for text, command in (
            ("打开浏览器检查登录", self.open_browser),
            ("抓取当前页面", self.capture_page),
            ("关闭浏览器窗口", self.close_browser),
            ("清理残留窗口", self.cleanup_leftovers),
            ("取消（正在打开时用）", lambda: self.app.stop_event.set()),
        ):
            button = ttk.Button(row, text=text, command=command)
            button.pack(side="left", padx=4)
            self.browser_buttons.append(button)
        ttk.Label(
            box,
            text="第一次用某个账号：点「打开浏览器检查登录」，如果窗口里要求登录，扫码登录一次即可长期有效；"
            "登录好后可以一直用这个窗口。页面改版时点「抓取当前页面」，把生成的目录发给助手更新规则。",
            font=SMALL_FONT,
            foreground="#666666",
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", padx=8)
        ttk.Label(box, textvariable=self.busy_var, font=SMALL_FONT, foreground="#0b5cad", wraplength=1000, justify="left").pack(
            anchor="w", padx=8, pady=(2, 8)
        )

    def _build_tools(self, parent: tk.Widget) -> None:
        box = ttk.LabelFrame(parent, text=" 其他 ")
        box.pack(fill="x", padx=12, pady=(6, 14))
        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=8)
        ttk.Button(row, text="重新加载设置", command=self.load_from_config).pack(side="left", padx=4)
        ttk.Button(row, text="运行环境自检", command=self.app.run_selftest).pack(side="left", padx=4)
        ttk.Button(row, text="打开配置文件（高级）", command=self.app.open_config).pack(side="left", padx=4)
        ttk.Button(row, text="打开工具目录", command=lambda: self.app.open_dir(cfgmod.BASE_DIR)).pack(side="left", padx=4)
        share = ttk.Frame(box)
        share.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(share, text="导出配置给同事", command=self.export_config_bundle).pack(side="left", padx=4)
        ttk.Button(share, text="导入同事的配置", command=self.import_config_bundle).pack(side="left", padx=4)
        ttk.Label(
            share,
            text="导出的是账号名单、网址、节奏和页面规则（不含本机浏览器路径）；同事导入后为每个账号扫码登录一次即可。",
            font=SMALL_FONT,
            foreground="#666666",
        ).pack(side="left", padx=6)
        ttk.Label(box, textvariable=self.url_var, font=SMALL_FONT, foreground="#666666", wraplength=1000, justify="left").pack(
            anchor="w", padx=8, pady=(0, 8)
        )

    # ---------- 读写 ----------
    def load_from_config(self) -> None:
        cfg = self.app.cfg
        creator = cfg.get("creator", {})
        jinniu = cfg.get("jinniu", {})
        self.publish_url.set(creator.get("publish_url") or "")
        self.works_url.set(creator.get("works_url") or "")
        self.jinniu_url.set(jinniu.get("video_library_url") or "")
        self.wait_after.set(str(creator.get("post_publish_wait_seconds", 10)))
        self.wait_account.set(str(creator.get("inter_account_wait_seconds", 30)))
        self.daily_limit.set(str(creator.get("daily_total_limit", 120)))
        order = (jinniu.get("list_order") or "newest_first").lower()
        for label, value in LIST_ORDER_LABELS.items():
            if value == order:
                self.list_order.set(label)
        mode = (jinniu.get("rename_mode") or "auto").lower()
        for label, value in RENAME_MODE_LABELS.items():
            if value == mode:
                self.rename_mode.set(label)
        self.rebuild_account_rows()
        choices = [row["name"].get().strip() for row in self.account_rows if row["name"].get().strip()]
        self.account_picker.configure(values=choices)
        if choices and self.target_account.get() not in choices:
            self.target_account.set(choices[0])

    def save_to_config(self, rebuild: bool = True) -> bool:
        cfg = self.app.cfg
        creator = cfg.setdefault("creator", {})
        jinniu = cfg.setdefault("jinniu", {})
        creator["publish_url"] = self.publish_url.get().strip()
        creator["works_url"] = self.works_url.get().strip()
        jinniu["video_library_url"] = cfgmod.strip_account_id(self.jinniu_url.get().strip())
        jinniu["list_order"] = LIST_ORDER_LABELS.get(self.list_order.get(), "newest_first")
        jinniu["rename_mode"] = RENAME_MODE_LABELS.get(self.rename_mode.get(), "auto")
        for key, var, minimum in (
            ("post_publish_wait_seconds", self.wait_after, 0),
            ("inter_account_wait_seconds", self.wait_account, 0),
            ("daily_total_limit", self.daily_limit, 1),
        ):
            try:
                creator[key] = max(minimum, int(float(var.get())))
            except Exception:
                messagebox.showwarning("数字填错了", "「%s」需要填数字，已保留原来的值。" % key, parent=self.app.root)
        accounts = cfg.setdefault("accounts", [])
        while len(accounts) < len(self.account_rows):
            accounts.append(cfgmod.default_account(len(accounts)))
        for index, row in enumerate(self.account_rows):
            if index >= len(accounts):
                break
            account = accounts[index]
            old_name = str(account.get("name") or "").strip()
            new_name = row["name"].get().strip() or cfgmod.default_account(index)["name"]
            if old_name and old_name != new_name and not account.get("browser_auto_dir"):
                old_copy = dict(account)
                old_copy["name"] = old_name
                old_dir = cfgmod.account_auto_dir(cfg, old_copy)
                if old_dir.exists():
                    account["browser_auto_dir"] = str(old_dir)
                    if not account.get("jinniu_chrome_auto_dir"):
                        account["jinniu_chrome_auto_dir"] = str(old_dir)
            account["name"] = new_name
            account["jinniu_account_id"] = row["account_id"].get().strip()
            apply_to_account(account, row["browser"].get(), row["login"].get(), self.browser_by_label)
        no_id = [
            row["name"].get().strip() or "账号"
            for index, row in enumerate(self.account_rows)
            if index < len(accounts)
            and accounts[index].get("enabled")
            and not row["account_id"].get().strip()
        ]
        if no_id:
            self.app.append_log(
                "提醒：这些账号还没填金牛账户ID（素材库地址里 __accountId__= 后面那串数字）——%s；"
                "第一次跑时会自动弹「选择账户」，识别到的 ID 会自动填回这里。" % "、".join(no_id)
            )
            self.app.set_status("提醒：%s 还没填金牛账户ID（首次运行会自动识别）" % "、".join(no_id))
        self.app.save_config()
        if rebuild:
            self.app.reload_from_config()
        self.app.set_status("设置已保存")
        self.app.append_log("设置已保存")
        return True

    # ---------- 操作 ----------
    def open_url(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            messagebox.showinfo("还没填地址", "请先把网址粘贴进输入框。", parent=self.app.root)
            return
        if not url.startswith("http"):
            url = "https://" + url
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showwarning("打不开", str(exc), parent=self.app.root)

    def target(self) -> Optional[Dict[str, Any]]:
        self.save_to_config(rebuild=False)
        name = self.target_account.get()
        for account in self.app.cfg.get("accounts", []):
            if (account.get("name") or "") == name:
                return account
        messagebox.showinfo("先选账号", "请先在上面选择要对哪个账号操作。", parent=self.app.root)
        return None

    def open_browser(self) -> None:
        account = self.target()
        if account is None:
            return
        mode = {
            "创作者平台发布页": "creator",
            "磁力金牛视频库": "jinniu",
            "空白页": "setup",
        }.get(self.page_picker.get(), "creator")
        self.app.stop_event.clear()
        self.busy_var.set("正在打开浏览器窗口…通常 5~15 秒，如果超过 15 秒会自动检查残留窗口并重试。")
        self.set_browser_buttons_enabled(False)
        self.app.run_background(lambda: self._open_browser_job(account, mode), "正在打开浏览器窗口…")

    def set_browser_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in getattr(self, "browser_buttons", []):
            try:
                button.configure(state=state)
            except Exception:
                pass

    def _open_browser_job(self, account: Dict[str, Any], mode: str) -> None:
        from .session import AccountBrowser

        try:
            try:
                self.app.close_setup_browser()
            except Exception:
                pass
            browser = AccountBrowser(
                self.app.cfg, account, mode=mode, logger=self.app.logger,
                progress=self.app.set_status,
                should_stop=self.app.stop_event.is_set,
            )
            browser.start()
            self.app.setup_account_name = account.get("name") or ""
            self.app.setup_session = browser
            tip = "浏览器已打开（账号：%s）" % account.get("name")
            if not browser.reuse_login:
                tip += "。如果窗口里要求登录，请扫码登录一次，之后长期有效。"
            self.busy_var.set("%s 当前页面：%s" % (tip, browser.current_url()))
            self.app.set_status(tip)
            for item in self.app.cfg.get("accounts", []):
                if (item.get("name") or "") == (self.app.setup_account_name or ""):
                    item["browser_ready"] = True
            self.app.save_config()
        finally:
            self.set_browser_buttons_enabled(True)

    def capture_page(self) -> None:
        browser = self.app.setup_session
        if browser is None or not browser.alive():
            messagebox.showinfo("先打开浏览器", "请先点「打开浏览器检查登录」，在窗口里点到要抓取的页面。", parent=self.app.root)
            return

        def job() -> None:
            info = browser.capture("设置页抓取")
            files = info.get("files") or []
            if not files:
                raise RuntimeError(
                    "抓取没有写出任何文件（%s）。请确认浏览器窗口里页面已经加载出来，再点一次。"
                    % (info.get("error") or "原因未知")
                )
            self.busy_var.set(
                "已抓取 %s 个元素、%d 个文件，保存到：%s" % (info.get("element_count", "?"), len(files), info.get("folder"))
            )
            self.app.append_log("页面快照已保存：%s" % info.get("folder"))
            self.app.set_status("页面快照已保存，可发给助手更新页面规则")

        self.app.run_background(job, "正在抓取当前页面…")

    def close_browser(self) -> None:
        self.app.close_setup_browser()
        self.busy_var.set("浏览器窗口已关闭")
        self.app.set_status("浏览器窗口已关闭")

    def cleanup_leftovers(self) -> None:
        """关掉以前遗留的自动化浏览器窗口（不含你日常用的浏览器）。"""
        from .browser import close_processes, processes_using

        root = cfgmod.expand_path(self.app.cfg.get("automation_data_dir") or "")
        pids = processes_using(root) if root else []
        if not pids:
            messagebox.showinfo("没有残留窗口", "没有发现残留的自动化浏览器窗口。", parent=self.app.root)
            return
        close_processes(pids, self.app.logger)
        self.busy_var.set("已清理 %d 个残留的自动化浏览器窗口" % len(pids))
        self.app.append_log("已清理 %d 个残留的自动化浏览器进程" % len(pids))
        self.app.set_status("已清理残留窗口，可以重新点了")

    # ---------- 配置导出 / 导入 ----------
    MACHINE_KEYS = (
        "browser_exe",
        "browser_source_user_data",
        "browser_source_profile",
        "browser_auto_dir",
        "jinniu_chrome_source_profile",
        "jinniu_chrome_auto_dir",
    )

    def export_config_bundle(self) -> None:
        import copy as _copy
        import json

        from tkinter import filedialog

        self.save_to_config(rebuild=False)
        cfg = _copy.deepcopy(self.app.cfg)
        for account in cfg.get("accounts", []):
            for key in self.MACHINE_KEYS:
                account.pop(key, None)
            account["browser_login"] = "新建扫码登录（每台电脑各自登录一次）"
        cfg.pop("automation_data_dir", None)
        try:
            selectors = json.loads(cfgmod.SELECTORS_PATH.read_text(encoding="utf-8"))
        except Exception:
            selectors = {}
        bundle = {"kind": "kuaishou-auto-helper", "version": 1, "config": cfg, "selectors": selectors}
        path = filedialog.asksaveasfilename(
            parent=self.app.root,
            title="把配置保存到",
            defaultextension=".json",
            initialfile="快手助手配置.json",
            filetypes=[("配置文件", "*.json")],
        )
        if not path:
            return
        Path(path).write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo(
            "导出完成",
            "配置已导出到：\n%s\n\n同事在新电脑上：双击启动工具 → 设置页点「导入同事的配置」→ "
            "再为每个账号点一次「打开浏览器检查登录」扫码登录即可。" % path,
            parent=self.app.root,
        )
        self.app.append_log("配置已导出：%s" % path)

    def import_config_bundle(self) -> None:
        import copy as _copy
        import json

        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self.app.root, title="选择配置文件", filetypes=[("配置文件", "*.json"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            bundle = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showwarning("读不了这个文件", str(exc), parent=self.app.root)
            return
        if not isinstance(bundle, dict) or bundle.get("kind") != "kuaishou-auto-helper":
            messagebox.showwarning("文件格式不对", "请选择用「导出配置给同事」生成的那个配置文件。", parent=self.app.root)
            return
        incoming = bundle.get("config") or {}
        current = self.app.cfg
        merged = _copy.deepcopy(incoming)
        merged["automation_data_dir"] = current.get("automation_data_dir") or "%LOCALAPPDATA%\\KuaishouAuto"
        for account in merged.get("accounts", []):
            for key in self.MACHINE_KEYS:
                account.pop(key, None)
            account["browser_name"] = ""
        cfgmod.save_config(merged)
        if bundle.get("selectors"):
            cfgmod.SELECTORS_PATH.write_text(
                json.dumps(bundle["selectors"], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        self.app.reload_from_config()
        messagebox.showinfo(
            "导入完成",
            "配置和页面规则都导入好了（共 %d 个账号）。\n\n下一步：到「浏览器窗口」里为每个账号点「打开浏览器检查登录」扫码登录一次。"
            % len(merged.get("accounts", [])),
            parent=self.app.root,
        )
        self.app.append_log("已导入配置：%s" % path)
