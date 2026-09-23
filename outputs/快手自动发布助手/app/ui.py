# -*- coding: utf-8 -*-
"""主界面：面向非技术使用者的可视化客户端。"""
from __future__ import annotations

import os
import queue
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

import tkinter as tk
from tkinter import messagebox, ttk

from . import config as cfgmod
from .bridge import Bridge, safe_name
from .browser import SleepGuard, list_chrome_profiles
from .copystore import CopyStore
from .copytext import validate
from .errors import StoppedByUser
from .flow_creator import CreatorContext
from .flow_creator import run_account as run_creator_account
from .flow_jinniu import JinniuContext
from .flow_jinniu import run_account as run_jinniu_account
from .logger import setup_logger
from .pending import PendingRenameStore
from .parallel import preflight_parallel, run_parallel_jobs
from .publish_settings import (
    format_publish_at,
    has_scheduled,
    normalize_publish_at,
    setting_key,
    settings_for_videos,
    summarize_author,
    validate_publish_at,
)
from .report import write_report
from .session import AccountBrowser
from .state import RunState
from .ui_cards import AccountCard, BIG_FONT, LABEL_FONT, SMALL_FONT
from .ui_dialogs import UiRequest, rescue_dialog, table_dialog, text_dialog
from .ui_help import build_help_tab
from .ui_settings import build_settings_tab
from .ui_wizard import SetupWizard
from .videos import human_size, list_videos

APP_TITLE = "快手自动发布助手"
REPORT_DIR_NAME = "报表"


class UiBridge(Bridge):
    """把流程里的日志、确认、人工接管请求接到界面上。"""

    def __init__(self, app: "AutoApp") -> None:
        self.app = app

    def _call(self, fn):
        if threading.current_thread() is threading.main_thread():
            return fn()
        request = UiRequest(fn)
        self.app.requests.put(request)
        return request.wait()

    def log(self, message: str, *args) -> None:
        self.app.append_log(message % args if args else message)

    def status(self, text: str) -> None:
        self.app.set_status(text)

    def progress(self, done: int, total: int) -> None:
        self.app.set_progress(done, total)

    def stopped(self) -> bool:
        return self.app.stop_event.is_set()

    def confirm(self, title: str, message: str) -> bool:
        def job():
            with self.app._ui_lock:
                return messagebox.askyesno(title, message, parent=self.app.root)

        return bool(self._call(job))

    def confirm_table(self, title, message, headers, rows) -> bool:
        def job():
            with self.app._ui_lock:
                return table_dialog(self.app.root, title, message, headers, rows)

        return bool(self._call(job))

    def plan_editor(self, account, videos, copies, mode: str = "confirm") -> bool:
        def job():
            with self.app._ui_lock:
                return self.app.open_plan_editor(account, videos, copies, mode=mode)

        return bool(self._call(job))

    def rescue(self, title: str, message: str, options: Sequence[str]) -> str:
        def job():
            with self.app._ui_lock:
                return rescue_dialog(self.app.root, title, message, options)

        return str(self._call(job))

    def shot(self, page, name: str) -> str:
        try:
            cfgmod.SHOT_DIR.mkdir(parents=True, exist_ok=True)
            target = cfgmod.SHOT_DIR / ("%s_%s.png" % (datetime.now().strftime("%H%M%S"), safe_name(name)))
            page.screenshot(path=str(target), full_page=False)
            return str(target)
        except Exception:
            return ""


class TaskBridge(Bridge):
    """并行账号任务使用的桥接器：日志带账号名，停止事件按账号隔离。"""

    def __init__(self, app: "AutoApp", account_name: str, stop_event: threading.Event) -> None:
        self.app = app
        self.account_name = account_name
        self.stop_event = stop_event

    def log(self, message: str, *args) -> None:
        text = message % args if args else message
        self.app.append_log("[%s] %s" % (self.account_name, text))

    def status(self, text: str) -> None:
        self.app.set_account_status(self.account_name, text)

    def progress(self, done: int, total: int) -> None:
        self.app.set_account_progress(self.account_name, done, total)

    def stopped(self) -> bool:
        return self.stop_event.is_set() or self.app.stop_event.is_set()

    def confirm(self, title: str, message: str) -> bool:
        return self.app.bridge.confirm("[%s] %s" % (self.account_name, title), message)

    def confirm_table(self, title, message, headers, rows) -> bool:
        return self.app.bridge.confirm_table(
            "[%s] %s" % (self.account_name, title),
            message,
            headers,
            rows,
        )

    def plan_editor(self, account, videos, copies, mode: str = "confirm") -> bool:
        return self.app.bridge.plan_editor(account, videos, copies, mode=mode)

    def rescue(self, title: str, message: str, options: Sequence[str]) -> str:
        return self.app.bridge.rescue(
            "[%s] %s" % (self.account_name, title),
            message,
            options,
        )

    def shot(self, page, name: str) -> str:
        return self.app.bridge.shot(page, "%s_%s" % (self.account_name, name))


class AutoApp:
    def __init__(self) -> None:
        cfgmod.ensure_dirs()
        self.cfg = cfgmod.load_config()
        self.report_dir = cfgmod.BASE_DIR / REPORT_DIR_NAME
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1280x940")
        self.root.minsize(1024, 700)
        self._setup_style()

        self.requests: "queue.Queue[UiRequest]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None
        self._ui_lock = threading.RLock()
        self._tasks_lock = threading.RLock()
        self.tasks: dict = {}
        self.active_browsers: dict = {}
        self.cards: List[AccountCard] = []
        self.refresh_job: Optional[str] = None
        self.log_lines: List[str] = []
        self.setup_session: Optional[AccountBrowser] = None
        self.active_browser: Optional[AccountBrowser] = None
        self.setup_account_name = ""
        self.setup_mode = tk.StringVar(value="creator")
        self._run_started = 0.0
        self._run_done = 0
        self._run_total = 0
        self.auto_rename = tk.BooleanVar(value=True)
        self.publish_settings: dict = {}
        self.pending = PendingRenameStore().load()

        self.bridge = UiBridge(self)
        self.state = RunState.load(cfgmod.RUN_DIR, datetime.now().strftime("%Y-%m-%d"))
        self._load_publish_settings_from_state()
        self.copy_store = CopyStore().load()
        self.logger = setup_logger(cfgmod.LOG_DIR, ui_sink=self.append_log)
        self._build()
        self.load_into_cards()
        self.refresh_all()
        self.root.after(150, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(700, self._maybe_first_run)
        self.root.after(1200, self._maybe_remind_pending_rename)
        self.root.after(60, self._center_main_window)

    def _center_main_window(self) -> None:
        """把客户端主窗口摆到屏幕中间（弹窗是以它为中心显示的，主窗口偏了弹窗也会偏）。"""
        try:
            self.root.update_idletasks()
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            width = min(1280, max(screen_w - 60, 900))
            height = min(940, max(screen_h - 120, 640))
            x = max((screen_w - width) // 2, 0)
            y = max((screen_h - height) // 3, 0)
            self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))
        except Exception:
            pass

    # ---------- 视觉与布局 ----------
    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure(".", font=LABEL_FONT)
        style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 11), padding=(22, 8))
        style.configure("Big.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(14, 8))
        style.configure("Go.TButton", font=("Microsoft YaHei UI", 13, "bold"), padding=(20, 12))
        style.configure("Status.TLabel", font=BIG_FONT)

    def _build(self) -> None:
        head = ttk.Frame(self.root)
        head.pack(fill="x", padx=14, pady=(10, 4))
        ttk.Label(head, text="快手自动发布助手", font=("Microsoft YaHei UI", 15, "bold")).pack(side="left")
        ttk.Label(
            head,
            text="创作者平台自动发布 + 磁力金牛素材名自动回改",
            font=SMALL_FONT,
            foreground="#666666",
        ).pack(side="left", padx=10)
        self.date_label = ttk.Label(head, text="", font=SMALL_FONT, foreground="#666666")
        self.date_label.pack(side="right")
        header_buttons = ttk.Frame(head)
        header_buttons.pack(side="right", padx=8)
        ttk.Button(header_buttons, text="引导设置", command=self.open_wizard).pack(side="left", padx=3)
        ttk.Button(header_buttons, text="打开日志", command=lambda: self.open_dir(cfgmod.LOG_DIR)).pack(side="left", padx=3)
        ttk.Button(header_buttons, text="打开报表", command=lambda: self.open_dir(self.report_dir)).pack(side="left", padx=3)
        ttk.Button(header_buttons, text="今日进度", command=self.show_state).pack(side="left", padx=3)
        ttk.Button(header_buttons, text="重置今日进度", command=self.reset_today).pack(side="left", padx=3)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.tab_today = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_today, text="  今天要发的  ")
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_settings, text="  设置  ")
        self.tab_help = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_help, text="  使用帮助  ")

        self._build_today()
        self.settings_tab = build_settings_tab(self.tab_settings, self)
        self.settings_tab.frame.pack(fill="both", expand=True)
        self.help_tab = build_help_tab(self.tab_help, self)
        self.help_tab.frame.pack(fill="both", expand=True)

    def _build_today(self) -> None:
        self.tip_var = tk.StringVar(value="")
        ttk.Label(
            self.tab_today,
            textvariable=self.tip_var,
            font=LABEL_FONT,
            foreground="#b35c00",
            wraplength=1180,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(8, 0))

        ttk.Label(
            self.tab_today,
            text="① 选好每个账号的素材文件夹　② 把广告语粘贴进对应输入框　③ 点下面的「开始上传发布」",
            font=LABEL_FONT,
            foreground="#0b5cad",
        ).pack(anchor="w", padx=12, pady=(6, 2))

        holder = ttk.Frame(self.tab_today)
        holder.pack(fill="both", expand=True, padx=8)
        canvas = tk.Canvas(holder, highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        self.cards_canvas = canvas

        def cards_wheel(event):
            try:
                node = self.root.winfo_containing(event.x_root, event.y_root)
            except Exception:
                node = None
            while node is not None:
                if node == canvas:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return "break"
                node = getattr(node, "master", None)
            return None

        canvas.bind_all("<MouseWheel>", cards_wheel, add="+")
        self.cards_container = inner

        cards_bar = ttk.Frame(self.tab_today)
        cards_bar.pack(fill="x", padx=14, pady=(2, 0))
        self.account_count_label = ttk.Label(cards_bar, text="", font=SMALL_FONT, foreground="#666666")
        self.account_count_label.pack(side="left")

        action_box = ttk.LabelFrame(self.tab_today, text=" 开始干活 ")
        action_box.pack(fill="x", padx=12, pady=(6, 4))
        bar = ttk.Frame(action_box)
        bar.pack(fill="x", padx=8, pady=8)
        self.btn_dry = ttk.Button(bar, text="仅演练（不发布）", style="Big.TButton", command=lambda: self.start_run("dry"))
        self.btn_dry.pack(side="left", padx=4)
        self.btn_publish = ttk.Button(bar, text="▶ 开始上传发布", style="Go.TButton", command=lambda: self.start_run("publish"))
        self.btn_publish.pack(side="left", padx=10)
        self.btn_parallel = ttk.Button(
            bar,
            text="▶ 同时开始上传发布",
            style="Go.TButton",
            command=lambda: self.start_run("publish", parallel=True),
        )
        self.btn_parallel.pack(side="left", padx=10)
        self.btn_rename = ttk.Button(bar, text="只改金牛素材名", style="Big.TButton", command=lambda: self.start_run("rename"))
        self.btn_rename.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(bar, text="⏹ 停止", style="Big.TButton", command=self.stop_run, state="disabled")
        self.btn_stop.pack(side="right", padx=4)
        self.confirm_run = tk.BooleanVar(
            value=bool(self.cfg.get("creator", {}).get("confirm_before_run", True))
        )
        self.confirm_rename = tk.BooleanVar(
            value=bool(self.cfg.get("jinniu", {}).get("confirm_mapping", False))
        )
        options_bar = ttk.Frame(action_box)
        options_bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Checkbutton(
            options_bar,
            text="上传发布完成后自动改名",
            variable=self.auto_rename,
        ).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(
            options_bar,
            text="上传前确认对照表",
            variable=self.confirm_run,
            command=self.save_toggles,
        ).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(
            options_bar,
            text="改名前确认对照表",
            variable=self.confirm_rename,
            command=self.save_toggles,
        ).pack(side="left")

        status_row = ttk.Frame(self.tab_today)
        status_row.pack(fill="x", padx=14, pady=(4, 0))
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(status_row, textvariable=self.status_var, style="Status.TLabel", foreground="#0b5cad").pack(anchor="w")
        self.progress = ttk.Progressbar(self.tab_today, mode="determinate")
        self.progress.pack(fill="x", padx=14, pady=(6, 0))
        self.progress_var = tk.StringVar(value="")
        ttk.Label(self.tab_today, textvariable=self.progress_var, font=SMALL_FONT, foreground="#666666").pack(anchor="w", padx=14)

        log_head = ttk.Frame(self.tab_today)
        log_head.pack(fill="x", padx=14, pady=(8, 0))
        self.show_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(log_head, text="显示详细日志（一般不用看）", variable=self.show_log, command=self._toggle_log).pack(side="left")
        self.log_frame = ttk.Frame(self.tab_today)
        self.log_text = tk.Text(self.log_frame, height=8, wrap="char", font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        log_xscroll = ttk.Scrollbar(self.log_frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scroll.set, xscrollcommand=log_xscroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        log_xscroll.grid(row=1, column=0, sticky="ew")
        self.log_frame.rowconfigure(0, weight=1)
        self.log_frame.columnconfigure(0, weight=1)

    def _toggle_log(self) -> None:
        if self.show_log.get():
            self.log_frame.pack(fill="both", expand=True, padx=14, pady=(2, 10))
        else:
            self.log_frame.pack_forget()

    # ---------- 数据同步 ----------
    def load_into_cards(self) -> None:
        self.rebuild_cards()

    def rebuild_cards(self) -> None:
        """按配置里的账号数量重建卡片（账号可以随时加减）。"""
        for widget in list(self.cards_container.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass
        self.cards = []
        accounts = self.cfg.get("accounts", [])
        if not accounts:
            from tkinter import ttk as _ttk

            _ttk.Label(
                self.cards_container,
                text="还没有账号。请到「设置」页添加账号，或者点右上角「引导设置」三步配好。",
                font=LABEL_FONT,
                foreground="#888888",
            ).pack(anchor="w", padx=12, pady=16)
        for index, account in enumerate(accounts):
            card = AccountCard(self.cards_container, index, self)
            self._fill_card(card, account)
            self.cards.append(card)
        try:
            self.account_count_label.configure(text="共 %d 个账号" % len(accounts))
        except Exception:
            pass

    def _fill_card(self, card: AccountCard, account) -> None:
        card.enabled.set(bool(account.get("enabled")))
        card.name_var.set(account.get("name") or "")
        card.dir_var.set(account.get("video_dir") or "")
        saved = self.copy_store.get(account.get("name") or "")
        card.set_copies(saved.get("raw", ""), saved.get("strip_index", False), saved.get("batch", False))

    def save_copies(self, card) -> None:
        name = card.name_var.get().strip()
        if not name:
            return
        self.copy_store.set(name, card.raw_text, card.strip_index, card.batch)

    def save_from_cards(self) -> None:
        accounts = self.cfg.setdefault("accounts", [])
        if len(accounts) < len(self.cards):
            for index in range(len(accounts), len(self.cards)):
                accounts.append(cfgmod.default_account(index))
        for index, card in enumerate(self.cards):
            if index >= len(accounts):
                break
            account = accounts[index]
            account["enabled"] = bool(card.enabled.get())
            account["video_dir"] = card.dir_var.get().strip()
        self.cfg["accounts"] = accounts
        cfgmod.save_config(self.cfg)

    def save_config(self) -> None:
        cfgmod.save_config(self.cfg)

    def save_toggles(self) -> None:
        """把界面上的两个"要不要弹窗"开关写进配置。"""
        try:
            self.cfg.setdefault("creator", {})["confirm_before_run"] = bool(self.confirm_run.get())
            self.cfg.setdefault("jinniu", {})["confirm_mapping"] = bool(self.confirm_rename.get())
            self.save_config()
            self.append_log(
                "设置已更新：上传前确认=%s，改名前确认=%s"
                % ("开" if self.confirm_run.get() else "关", "开" if self.confirm_rename.get() else "关")
            )
        except Exception:
            pass

    def schedule_refresh(self) -> None:
        if self.refresh_job is not None:
            try:
                self.root.after_cancel(self.refresh_job)
            except Exception:
                pass
        self.refresh_job = self.root.after(600, self.refresh_all)

    def account_plan(self, card) -> tuple:
        folder = card.dir_var.get().strip()
        videos = list_videos(folder) if folder else []
        return videos, card.copies(len(videos))

    def refresh_all(self) -> None:
        self.refresh_job = None
        for card in self.cards:
            card.refresh()
        self.save_from_cards()
        self.date_label.configure(text="今天是 " + datetime.now().strftime("%Y年%m月%d日"))
        self._refresh_tip()

    def _refresh_tip(self) -> None:
        issues = self.config_issues()
        if issues:
            self.tip_var.set("还没配置好：" + "；".join(issues) + "。点右上角「引导设置」，三步就能配完。")
            return
        ready = []
        for card in self.cards:
            if not card.enabled.get():
                continue
            videos, copies = self.account_plan(card)
            if videos and len(videos) == len(copies):
                ready.append("%s（%d 条）" % (card.name_var.get().strip(), len(videos)))
        if ready:
            self.tip_var.set("已就绪：" + "、".join(ready) + "，可以点「开始上传发布」了。")
        else:
            self.tip_var.set("请在要发的账号卡片里粘贴广告语，数量与视频一致后才好开跑。")

    def config_issues(self) -> List[str]:
        issues = []
        accounts = [a for a in self.cfg.get("accounts", []) if a.get("enabled")]
        if not accounts:
            issues.append("没有勾选要发的账号")
        if not (self.cfg.get("creator", {}).get("publish_url") or "").strip():
            issues.append("没填创作者平台发布页网址")
        if not (self.cfg.get("jinniu", {}).get("video_library_url") or "").strip():
            issues.append("没填磁力金牛视频库网址")
        return issues

    def _load_publish_settings_from_state(self) -> None:
        """把当天状态里已经保存的定时时间恢复到内存（作者声明按约定不恢复）。"""
        for item in self.state.items():
            path = str(item.get("path") or "")
            publish_at = str(item.get("publish_at") or "")
            if not path or not publish_at:
                continue
            key = setting_key(str(item.get("account") or ""), path)
            current = dict(self.publish_settings.get(key) or {})
            current["publish_at"] = publish_at
            current.setdefault("author_statement", "")
            self.publish_settings[key] = current

    def get_publish_setting(self, account_name: str, path: str) -> dict:
        key = setting_key(account_name, path)
        value = dict(self.publish_settings.get(key) or {})
        value.setdefault("author_statement", "")
        value.setdefault("publish_at", "")
        return value

    def save_publish_setting(
        self,
        account_name: str,
        index: int,
        file_name: str,
        path: str,
        values: dict,
    ) -> None:
        key = setting_key(account_name, path)
        data = dict(values or {})
        data["author_statement"] = str(data.get("author_statement") or "")
        data["publish_at"] = normalize_publish_at(data.get("publish_at"))
        self.publish_settings[key] = data
        # 定时时间要落盘，防止程序中断重开后误变成立即发布；
        # 作者声明只留在内存里，按用户要求不写入磁盘。
        try:
            self.state.mark(
                account_name,
                index,
                path=path,
                publish_mode=("定时发布" if data.get("publish_at") else "立即发布"),
                publish_at=data.get("publish_at", ""),
            )
        except Exception as exc:
            self.append_log("保存定时时间失败：%s" % exc)

    def open_plan_editor(self, account, videos, copies, mode: str = "preview") -> bool:
        from .ui_plan import PlanEditorDialog

        account_name = account.get("name") or ""

        def getter(path: str) -> dict:
            return self.get_publish_setting(account_name, path)

        def setter(index: int, path: str, values: dict) -> None:
            self.save_publish_setting(
                account_name,
                index,
                Path(path).name,
                path,
                values,
            )

        return PlanEditorDialog(
            self.root,
            account_name,
            videos,
            copies,
            getter,
            setter,
            creator_cfg=self.cfg.get("creator", {}),
            mode=mode,
        ).show()

    def _maybe_remind_pending_rename(self) -> None:
        items = self.pending.entries()
        if not items:
            return
        lines = []
        for item in items[:8]:
            when = str(item.get("publish_at") or "").replace("T", " ")[:16]
            lines.append("· %s：%s%s" % (item.get("account", ""), item.get("file", ""), ("（%s）" % when) if when else ""))
        self.append_log("有 %d 条定时发布素材待手动改金牛素材名" % len(items))
        answer = rescue_dialog(
            self.root,
            "有定时发布的素材待改名",
            "有 %d 条定时发布的视频还没有改金牛素材名。\n\n%s\n\n"
            "如果你已经在金牛素材库里手动改完了，点第一项清除待办；"
            "否则请稍后手动点「只改金牛素材名」。"
            % (len(items), "\n".join(lines)),
            ["我已经改完名了，清除待办", "稍后再说"],
        )
        if answer == "我已经改完名了，清除待办":
            removed = self.pending.clear_all()
            self.append_log("已清除 %d 条待改金牛素材名待办（用户确认已手动改完）" % removed)

    def preview_account(self, card) -> None:
        videos, copies = self.account_plan(card)
        if not videos:
            messagebox.showinfo("没有视频", "这个账号的素材文件夹里还没有视频。", parent=self.root)
            return
        account = self.cfg["accounts"][card.index] if card.index < len(self.cfg.get("accounts", [])) else {}
        self.open_plan_editor(
            account,
            videos,
            copies,
            mode="preview",
        )

    # ---------- 界面辅助 ----------
    def _poll(self) -> None:
        while True:
            try:
                request = self.requests.get_nowait()
            except queue.Empty:
                break
            request.run()
        self.root.after(150, self._poll)

    def append_log(self, text: str) -> None:
        line = str(text).rstrip()
        self.log_lines.append(line)
        if len(self.log_lines) > 800:
            self.log_lines = self.log_lines[-800:]

        def write() -> None:
            try:
                self.log_text.insert("end", line + "\n")
                if int(self.log_text.index("end-1c").split(".")[0]) > 3000:
                    self.log_text.delete("1.0", "500.0")
                self.log_text.see("end")
            except Exception:
                pass

        try:
            if threading.current_thread() is threading.main_thread():
                write()
            else:
                self.root.after(0, write)
        except Exception:
            pass

    def recent_log_text(self, count: int = 60) -> str:
        return "\n".join(self.log_lines[-count:])

    def is_running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def register_task(self, name: str, stop_event: threading.Event, total: int) -> None:
        with self._tasks_lock:
            self.tasks[name] = {
                "stop_event": stop_event,
                "status": "排队中",
                "done": 0,
                "total": int(total or 0),
                "current": "",
            }
        self._refresh_task_cards()
        self._update_overall_progress()

    def unregister_task(self, name: str) -> None:
        with self._tasks_lock:
            self.tasks.pop(name, None)
        self._refresh_task_cards()
        self._update_overall_progress()

    def register_browser(self, name: str, browser) -> None:
        with self._tasks_lock:
            self.active_browsers[name] = browser
        if name in self.tasks:
            self.set_account_status(name, "浏览器已打开")

    def unregister_browser(self, name: str) -> None:
        with self._tasks_lock:
            self.active_browsers.pop(name, None)

    def set_account_status(self, name: str, text: str) -> None:
        with self._tasks_lock:
            task = self.tasks.get(name)
            if task is not None:
                task["status"] = str(text or "")
        self.set_status("[%s] %s" % (name, text))
        self._refresh_task_cards()

    def set_account_progress(self, name: str, done: int, total: int, current: str = "") -> None:
        with self._tasks_lock:
            task = self.tasks.get(name)
            if task is not None:
                task["done"] = int(done or 0)
                task["total"] = int(total or 0)
                if current:
                    task["current"] = str(current)
        self._refresh_task_cards()
        self._update_overall_progress()

    def _task_card(self, name: str):
        for card in self.cards:
            if card.name_var.get().strip() == name:
                return card
        return None

    def _refresh_task_cards(self) -> None:
        def job() -> None:
            with self._tasks_lock:
                snapshot = {key: dict(value) for key, value in self.tasks.items()}
            for name, task in snapshot.items():
                card = self._task_card(name)
                if card is None:
                    continue
                done = int(task.get("done") or 0)
                total = int(task.get("total") or 0)
                progress = "第 %d/%d 条" % (done, total) if total else ""
                if task.get("current"):
                    progress += " · %s" % task.get("current")
                card.set_task_state(str(task.get("status") or ""), progress)
        try:
            if threading.current_thread() is threading.main_thread():
                job()
            else:
                self.root.after(0, job)
        except Exception:
            pass

    def _update_overall_progress(self) -> None:
        def job() -> None:
            with self._tasks_lock:
                tasks = [dict(value) for value in self.tasks.values()]
            if not tasks:
                return
            done = sum(int(item.get("done") or 0) for item in tasks)
            total = sum(int(item.get("total") or 0) for item in tasks)
            try:
                self.progress["maximum"] = max(total, 1)
                self.progress["value"] = done
                self.progress_var.set(
                    "并行运行中：%d 个账号 · 已完成 %d / %d 条"
                    % (len(tasks), done, total)
                )
            except Exception:
                pass
        try:
            if threading.current_thread() is threading.main_thread():
                job()
            else:
                self.root.after(0, job)
        except Exception:
            pass

    def stop_account(self, name: str) -> None:
        name = str(name or "").strip()
        if not name:
            return
        with self._tasks_lock:
            task = self.tasks.get(name)
            browser = self.active_browsers.get(name)
            if task is not None:
                task["stop_event"].set()
                task["status"] = "已请求停止"
        self.append_log("收到停止请求：%s" % name)
        if browser is not None:
            threading.Thread(target=self._close_browser, args=(browser,), daemon=True).start()
        self._refresh_task_cards()

    def _close_browser(self, browser) -> None:
        try:
            browser.close()
        except Exception:
            pass

    def set_status(self, text: str) -> None:
        def job() -> None:
            try:
                self.status_var.set(text)
            except Exception:
                pass

        try:
            if threading.current_thread() is threading.main_thread():
                job()
            else:
                self.root.after(0, job)
        except Exception:
            pass

    def set_progress(self, done: int, total: int) -> None:
        def job() -> None:
            try:
                self.progress["maximum"] = max(total, 1)
                self.progress["value"] = done
                self._run_done = done
                self._run_total = total
                self._update_progress_text()
            except Exception:
                pass

        try:
            if threading.current_thread() is threading.main_thread():
                job()
            else:
                self.root.after(0, job)
        except Exception:
            pass

    def _update_progress_text(self) -> None:
        total = self._run_total
        done = self._run_done
        if not total:
            self.progress_var.set("")
            return
        text = "已完成 %d / %d 条" % (done, total)
        if done > 0 and self._run_started:
            elapsed = time.time() - self._run_started
            pace = elapsed / done
            remain = pace * max(total - done, 0)
            text += " · 已用 %s · 预计还需 %s" % (self._fmt_duration(elapsed), self._fmt_duration(remain))
        else:
            text += " · 正在估算剩余时间…"
        self.progress_var.set(text)

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        seconds = int(max(seconds, 0))
        hours, remain = divmod(seconds, 3600)
        minutes = remain // 60
        if hours:
            return "%d 小时 %d 分" % (hours, minutes)
        if minutes:
            return "%d 分钟" % minutes
        return "%d 秒" % seconds

    def human_size(self, num_bytes: float) -> str:
        return human_size(num_bytes)

    def open_dir(self, folder) -> None:
        try:
            path = Path(folder)
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showwarning("打不开目录", str(exc), parent=self.root)

    def open_config(self) -> None:
        self.save_from_cards()
        try:
            os.startfile(str(cfgmod.CONFIG_PATH))
        except Exception:
            self.open_dir(cfgmod.CONFIG_DIR)

    def profile_choices(self):
        from .loginconfig import browser_by_label, default_browser_label

        accounts = self.cfg.get("accounts") or [{}]
        label = accounts[0].get("browser_name") or default_browser_label()
        info = browser_by_label().get(label) or {}
        user_data = accounts[0].get("browser_source_user_data") or info.get("user_data_dir") or ""
        return list_chrome_profiles(cfgmod.expand_path(user_data))

    def reload_from_config(self, keep_cards: bool = False) -> None:
        self.cfg = cfgmod.load_config()
        if not keep_cards:
            self.load_into_cards()
        self.settings_tab.load_from_config()
        self.refresh_all()

    def open_wizard(self) -> None:
        SetupWizard(self)

    def _maybe_first_run(self) -> None:
        if self.config_issues() and not any(card.enabled.get() for card in self.cards):
            SetupWizard(self)

    def show_state(self) -> None:
        self.state = RunState.load(cfgmod.RUN_DIR, datetime.now().strftime("%Y-%m-%d"))
        items = self.state.items()
        if not items:
            messagebox.showinfo("今日进度", "今天还没有运行记录。", parent=self.root)
            return
        rows = [
            (
                item.get("account", ""),
                int(item.get("index", 0)) + 1,
                item.get("file", "") or Path(str(item.get("path") or "")).name,
                item.get("path", ""),
                summarize_author(item.get("_author_statement", "")),
                format_publish_at(item.get("publish_at", "")),
                item.get("publish_mode", "") or ("定时发布" if item.get("publish_at") else "立即发布"),
                item.get("publish_status", ""),
                item.get("rename_status", ""),
                str(item.get("skip_reason", ""))[:36],
                str(item.get("note", ""))[:30],
            )
            for item in sorted(items, key=lambda x: (str(x.get("account")), int(x.get("index", 0))))
        ]
        published = sum(1 for item in items if item.get("publish_status") == "已发布")
        clear_requested = table_dialog(
            self.root,
            "今日进度",
            self.state.summary()
            + "　（关闭窗口不会清空；只有点「清空今天的记录」才会清空）",
            [
                "账号",
                "序号",
                "文件名",
                "文件路径",
                "作者声明",
                "发布时间",
                "发布方式",
                "发布状态",
                "改名状态",
                "跳过原因",
                "备注",
            ],
            rows,
            confirm_text=("清空今天的记录（这些视频会重新发布）" if published else "关闭"),
            cancel_text=("关闭" if published else ""),
        )
        if published and clear_requested:
            self.state.reset()
            self.set_status("已清空今日记录，可以重新发布了")
            self.append_log("已清空今日记录（清除了 %d 条已发布标记）" % published)

    def run_background(self, fn: Callable[[], Any], busy_text: str = "处理中…") -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("正在运行", "当前有任务在跑，请等它结束。", parent=self.root)
            return
        self.set_status(busy_text)

        def wrapper() -> None:
            try:
                fn()
            except Exception as exc:
                detail = traceback.format_exc()
                self.append_log("操作失败：%s" % exc)
                self.append_log(detail)
                try:
                    self.logger.error("操作失败：%s\n%s", exc, detail)
                except Exception:
                    pass
                self.set_status("操作失败：%s（详情见日志）" % exc)
                try:
                    tail = "\n".join([line for line in detail.strip().splitlines()[-4:]])
                    self.bridge.confirm("操作失败", "%s\n\n出错位置：\n%s\n\n（这段文字请截图发我）" % (exc, tail))
                except Exception:
                    pass

        self.worker = threading.Thread(target=wrapper, daemon=True)
        self.worker.start()

    def run_selftest(self) -> None:
        from .selftest import main as selftest_main

        def job() -> None:
            code = selftest_main()
            self.set_status("自检完成：%s" % ("全部通过" if code == 0 else "有项目未通过，详见日志"))

        self.run_background(job, "正在自检…")

    def close_setup_browser(self) -> None:
        if self.setup_session is not None:
            try:
                self.setup_session.close()
            except Exception:
                pass
        self.setup_session = None
        self.setup_account_name = ""

    # ---------- 运行 ----------
    def _validate_selection(self, mode: str):
        targets = []
        problems = []
        for card in self.cards:
            if not card.enabled.get():
                continue
            name = card.name_var.get().strip() or "未命名账号"
            videos, copies = self.account_plan(card)
            account = self.cfg["accounts"][card.index]
            if not videos:
                problems.append("%s：素材文件夹里没有视频" % name)
                continue
            if mode in ("dry", "publish"):
                result = validate(copies, len(videos))
                if not result.get("ok"):
                    problems.append("%s：%s" % (name, result.get("message")))
                    continue
            settings = settings_for_videos(name, videos, self.publish_settings)
            if mode in ("dry", "publish"):
                for item_index, setting in enumerate(settings, start=1):
                    problem = validate_publish_at(
                        setting.get("publish_at"),
                        min_lead_minutes=int(self.cfg.get("creator", {}).get("schedule_min_lead_minutes", 60)),
                        max_days=int(self.cfg.get("creator", {}).get("schedule_max_days", 14)),
                    )
                    if problem:
                        problems.append("%s：第 %d 条定时时间不合适（%s）" % (name, item_index, problem))
            targets.append((account, videos, copies, settings))
        return targets, problems

    def _set_running(self, running: bool) -> None:
        for button in (self.btn_dry, self.btn_publish, self.btn_rename, self.btn_parallel):
            try:
                button.configure(state="disabled" if running else "normal")
            except Exception:
                pass
        try:
            self.btn_stop.configure(state="normal" if running else "disabled")
        except Exception:
            pass
        for card in self.cards:
            try:
                card.set_running(running)
            except Exception:
                pass

    def start_run(self, mode: str, parallel: bool = False) -> None:
        if self.is_running():
            messagebox.showinfo("正在运行", "已经有一个任务在跑，请先等它结束或点停止。", parent=self.root)
            return
        issues = self.config_issues()
        if issues:
            if messagebox.askyesno("还没配置好", "现在有这些问题：\n\n%s\n\n要现在打开引导设置吗？" % "\n".join(issues), parent=self.root):
                self.open_wizard()
            return
        self.save_from_cards()
        targets, problems = self._validate_selection(mode)
        if problems:
            messagebox.showwarning("还不能开跑", "请先处理下面的问题：\n\n" + "\n".join(problems), parent=self.root)
            return
        if not targets:
            messagebox.showwarning("没有可跑的账号", "请在要发的账号卡片上打勾，并确认素材文件夹和广告语都填好了。", parent=self.root)
            return
        max_accounts = len(targets) if parallel else 1
        if parallel:
            problems = preflight_parallel(self.cfg, [item[0] for item in targets])
            if problems:
                messagebox.showwarning(
                    "不能并行运行",
                    "发现下面的冲突，请先处理，或改用普通串行方式：\n\n%s" % "\n".join(problems),
                    parent=self.root,
                )
                return
            if not bool(self.cfg.get("creator", {}).get("parallel_risk_acked")):
                if not messagebox.askyesno(
                    "并行运行风险提示",
                    "并行会同时打开多个浏览器、共用同一条网络，并同时访问平台。\n\n"
                    "可能出现：上传变慢、登录被顶、平台风控提示。\n"
                    "工具会保证单个账号内部仍然逐条串行，一个账号失败也只会停该账号；"
                    "但请先确认各账号登录和金牛账户都相互独立。\n\n确定开始并行运行吗？",
                    parent=self.root,
                ):
                    return
                self.cfg.setdefault("creator", {})["parallel_risk_acked"] = True
                self.save_config()
        pending_login = [
            item[0].get("name") for item in targets if not item[0].get("browser_ready")
        ]
        if pending_login:
            if not messagebox.askyesno(
                "这些账号还没做过登录检查",
                "以下账号还没有点过「打开浏览器检查登录」：\n\n%s\n\n"
                "第一次跑的时候脚本会自己打开浏览器窗口；如果窗口里要求登录，脚本会停下来等你扫码。\n"
                "想更稳妥的话，先去「设置」页点一次「打开浏览器检查登录」并扫码登录。\n\n"
                "现在就开始运行吗？" % "、".join(pending_login),
                parent=self.root,
            ):
                return
        if mode == "publish":
            total = sum(len(item[1]) for item in targets)
            limit = int(self.cfg.get("creator", {}).get("daily_total_limit", 120))
            extra = "\n注意：今天共 %d 条，超过了你设定的上限 %d 条。" % (total, limit) if total > limit else ""
            order_text = (
                "将同时运行你勾选的 %d 个账号；每个账号内部仍然逐条上传、逐条发布。"
                % len(targets)
                if parallel
                else "将按账号顺序一个一个来，每个账号开始前还会让你核对一次对照表。"
            )
            if not messagebox.askyesno(
                "确认开始真实发布",
                "%s\n\n本次共 %d 个账号、%d 条视频。%s\n\n确定开始吗？"
                % (order_text, len(targets), total, extra),
                parent=self.root,
            ):
                return
        if parallel and self.confirm_run.get():
            targets = self._confirm_parallel_targets(targets)
            if not targets:
                messagebox.showinfo("没有已确认的账号", "所有账号都被跳过了，本次不运行。", parent=self.root)
                return
            max_accounts = len(targets)
        self.stop_event.clear()
        with self._tasks_lock:
            self.tasks = {}
            self.active_browsers = {}
        self._run_started = time.time()
        self._run_done = 0
        self._run_total = sum(len(item[1]) for item in targets) or 1
        self.set_progress(0, self._run_total)
        for card in self.cards:
            card.set_task_state("", "")
        self._set_running(True)
        self.append_log("-" * 60)
        self.append_log(
            "开始运行：%s（模式：%s，%s）"
            % (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                mode,
                ("并行 %d 个账号" % max_accounts) if parallel else "串行",
            )
        )
        if parallel:
            self.worker = threading.Thread(
                target=self._run_parallel,
                args=(mode, list(targets), max_accounts),
                daemon=True,
            )
        else:
            self.worker = threading.Thread(
                target=self._run_worker,
                args=(mode, list(targets)),
                daemon=True,
            )
        self.worker.start()

    def stop_run(self) -> None:
        self.stop_event.set()
        self.set_status("正在停止…（会立刻关掉自动化浏览器窗口，让卡住的操作马上结束）")
        self.append_log("收到停止请求：正在中断当前操作…")
        with self._tasks_lock:
            tasks = list(self.tasks.values())
            browsers = list(self.active_browsers.values())
        for task in tasks:
            try:
                task["stop_event"].set()
            except Exception:
                pass
        for browser in browsers:
            threading.Thread(target=self._close_browser, args=(browser,), daemon=True).start()
        browser = getattr(self, "active_browser", None)
        if browser is not None:
            threading.Thread(target=self._force_close, args=(browser,), daemon=True).start()

    def _force_close(self, browser) -> None:
        try:
            browser.close()
            self.append_log("已关闭自动化浏览器窗口，当前操作已中断。")
        except Exception:
            pass

    def reset_today(self) -> None:
        """清空今天的发布记录，让所有视频重新处理一遍。"""
        if not messagebox.askyesno(
            "重置今日进度",
            "会清空工具里「今天已发布」的记录，重新运行时这些视频会再发一遍。\n"
            "同时会清除「定时发布待改金牛素材名」的待办（视为你已经处理完）。\n"
            "（已经发布出去的作品不会消失，只是会重复发布一次）\n\n确定要重置吗？",
            parent=self.root,
        ):
            return
        self.state = RunState.load(cfgmod.RUN_DIR, datetime.now().strftime("%Y-%m-%d"))
        self.state.reset()
        removed_pending = self.pending.clear_all()
        self.set_status("已重置今日进度，所有视频都会重新处理")
        self.append_log("已重置今日进度（清空断点记录）")
        if removed_pending:
            self.append_log("已清除 %d 条待改金牛素材名待办（重置今日进度视为已完成）" % removed_pending)

    def _run_worker_legacy(self, mode: str, targets) -> None:
        """旧版串行实现，保留作回滚参考；当前实际入口是后面的 _run_worker。"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        state = RunState.load(cfgmod.RUN_DIR, date_str)
        self.state = state
        creator_cfg = self.cfg.get("creator", {})
        total_items = sum(len(item[1]) for item in targets) or 1
        done_items = 0
        try:
            with SleepGuard():
                for position, target in enumerate(targets):
                    account, videos, copies = target[:3]
                    target_settings = (
                        list(target[3])
                        if len(target) > 3
                        else settings_for_videos(
                            account.get("name") or "未命名账号", videos, self.publish_settings
                        )
                    )
                    if self.stop_event.is_set():
                        self.append_log("已按你的要求停止。")
                        break
                    name = account.get("name") or "未命名账号"
                    self.set_status("【%s】准备中…" % name)
                    if mode in ("dry", "publish"):
                        already = [str(video) for video in videos if state.is_published_path(name, str(video))]
                        if already:
                            shown = "、".join(Path(item).name for item in already[:6])
                            answer = self.bridge.rescue(
                                "有视频被记录为「今天已发布」",
                                "账号「%s」有 %d 条视频在今天的记录里是「已发布」：\n%s\n\n"
                                "如果它们其实没发出去（比如之前浏览器异常被误判），选第一项重新发布一遍。"
                                % (name, len(already), shown),
                                ["全部重新发布一遍", "按记录跳过这些", "停止运行"],
                            )
                            if answer == "停止运行":
                                break
                            if answer == "全部重新发布一遍":
                                removed = state.clear_paths(name, already)
                                self.append_log("已清除 %d 条的「已发布」记录，这次会重新发布" % removed)
                    if mode in ("dry", "publish"):
                        ok = True
                        if self.confirm_run.get():
                            ok = self.bridge.plan_editor(account, videos, copies, mode="confirm")
                        else:
                            self.append_log("（已关闭上传前确认，直接开始）账号：%s" % name)
                        if not ok:
                            self.append_log("你跳过了账号：%s" % name)
                            continue
                        target_settings = settings_for_videos(name, videos, self.publish_settings)
                        setting_problems = []
                        for item_index, setting in enumerate(target_settings, start=1):
                            problem = validate_publish_at(
                                setting.get("publish_at"),
                                min_lead_minutes=int(creator_cfg.get("schedule_min_lead_minutes", 60)),
                                max_days=int(creator_cfg.get("schedule_max_days", 14)),
                            )
                            if problem:
                                setting_problems.append("第 %d 条：%s" % (item_index, problem))
                        if setting_problems:
                            self.append_log(
                                "账号「%s」的发布设置没有通过：%s"
                                % (name, "；".join(setting_problems))
                            )
                            self.bridge.confirm(
                                "发布设置需要修改",
                                "账号「%s」有设置问题，本次不会启动这个账号：\n\n%s"
                                % (name, "\n".join(setting_problems)),
                            )
                            continue
                    scheduled_present = has_scheduled(
                        {
                            setting_key(name, str(video)): setting
                            for video, setting in zip(videos, target_settings)
                        }
                    )
                    auto_rename_this = (
                        mode == "rename"
                        or (
                            mode == "publish"
                            and self.auto_rename.get()
                            and not (
                                scheduled_present
                                and not bool(creator_cfg.get("auto_rename_when_scheduled", False))
                            )
                        )
                    )
                    if mode == "publish" and scheduled_present and not auto_rename_this:
                        self.append_log("账号「%s」包含定时发布，已跳过自动改名，写入待改金牛素材名台账。" % name)
                    browser = None
                    try:
                        mode_for_browser = "jinniu" if mode == "rename" else "creator"
                        browser = AccountBrowser(
                            self.cfg, account, mode=mode_for_browser,
                            logger=self.logger, progress=self.set_status,
                            should_stop=self.stop_event.is_set,
                        )
                        browser.start()
                        page = browser.page
                        self.active_browser = browser
                        if mode in ("dry", "publish"):
                            ctx = CreatorContext(
                                self.bridge, page, self.cfg, account, videos, copies, state, self.logger,
                                video_settings=target_settings,
                                dry_run=(mode == "dry"),
                            )
                            result = run_creator_account(ctx)
                            if mode == "publish":
                                for scheduled in result.get("scheduled") or []:
                                    self.pending.add(
                                        name,
                                        scheduled.get("file", ""),
                                        scheduled.get("copy", ""),
                                        scheduled.get("publish_at", ""),
                                    )
                                if result.get("scheduled"):
                                    self.append_log(
                                        "已记录 %d 条定时发布的待改金牛素材名。"
                                        % len(result.get("scheduled") or [])
                                    )
                            if mode == "publish" and not result.get("published"):
                                self.append_log(
                                    "本次没有新发布的作品（可能都已发布过），跳过金牛改名，避免改错。"
                                )
                                done_items += len(videos)
                                self.set_progress(done_items, total_items)
                                continue
                        if auto_rename_this:
                            self.append_log("进入金牛改名阶段：%s" % name)
                            jctx = JinniuContext(
                                self.bridge, page, self.cfg, account, videos, copies, state, self.logger
                            )
                            run_jinniu_account(jctx, after_publish=(mode == "publish"))
                            renamed_files = [
                                str(item.get("file") or "")
                                for item in state.items()
                                if item.get("account") == name and item.get("rename_status") == "已改名"
                            ]
                            if renamed_files:
                                removed = self.pending.resolve(name, renamed_files)
                                if removed:
                                    self.append_log("已核销 %d 条待改金牛素材名台账。" % removed)
                    except Exception as exc:
                        self.append_log("账号「%s」中断：%s" % (name, exc))
                        self.append_log(traceback.format_exc())
                        if isinstance(exc, StoppedByUser) or self.stop_event.is_set():
                            self.append_log("已停止。")
                            break
                        if not self.stop_event.is_set() and position < len(targets) - 1:
                            if not self.bridge.confirm(
                                "账号中断",
                                "账号「%s」中断了：\n\n%s\n\n已经成功处理的部分不会重复发布。要继续下一个账号吗？"
                                % (name, exc),
                            ):
                                break
                    finally:
                        self.active_browser = None
                        if browser is not None:
                            try:
                                browser.close()
                            except Exception:
                                pass
                    done_items += len(videos)
                    self.set_progress(done_items, total_items)
                    wait_seconds = float(creator_cfg.get("inter_account_wait_seconds", 30))
                    if position < len(targets) - 1 and wait_seconds > 0 and not self.stop_event.is_set():
                        self.append_log("账号之间休息 %.0f 秒，然后切换下一个账号" % wait_seconds)
                        time.sleep(wait_seconds)
        except Exception as exc:
            self.append_log("运行中断：%s" % exc)
            self.append_log(traceback.format_exc())
        finally:
            try:
                report_path = write_report(self.report_dir / ("运行结果_%s.xlsx" % date_str), state.items())
                self.append_log("结果报表已生成：%s" % report_path)
            except Exception as exc:
                self.append_log("生成报表失败：%s" % exc)
            self.set_status("运行结束：" + state.summary())
            self.append_log("运行结束：" + state.summary())
            self._set_running(False)
            self._show_run_summary(state)

    def _confirm_parallel_targets(self, targets):
        confirmed = []
        for target in targets:
            account, videos, copies = target[:3]
            name = account.get("name") or "未命名账号"
            if self.open_plan_editor(account, videos, copies, mode="confirm"):
                settings = settings_for_videos(name, videos, self.publish_settings)
                confirmed.append((account, videos, copies, settings))
            else:
                self.append_log("你跳过了账号：%s" % name)
        return confirmed

    def _run_worker(self, mode: str, targets) -> None:
        """串行模式：账号一个接一个，每个账号内部逻辑与并行模式共用。"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        state = RunState.load(cfgmod.RUN_DIR, date_str)
        self.state = state
        creator_cfg = self.cfg.get("creator", {})
        total_items = sum(len(item[1]) for item in targets) or 1
        done_items = 0
        try:
            with SleepGuard():
                for position, target in enumerate(targets):
                    if self.stop_event.is_set():
                        self.append_log("已按你的要求停止。")
                        break
                    account, videos, copies = target[:3]
                    settings = (
                        list(target[3])
                        if len(target) > 3
                        else settings_for_videos(
                            account.get("name") or "未命名账号",
                            videos,
                            self.publish_settings,
                        )
                    )
                    name = account.get("name") or "未命名账号"
                    self.set_status("【%s】准备中…" % name)
                    result = self._run_one_account(
                        mode,
                        account,
                        videos,
                        copies,
                        settings,
                        state,
                        self.bridge,
                        task_event=None,
                        confirm_plan=True,
                    )
                    if result.get("stopped"):
                        break
                    if result.get("error"):
                        if position < len(targets) - 1 and not self.stop_event.is_set():
                            if not self.bridge.confirm(
                                "账号中断",
                                "账号「%s」中断了：\n\n%s\n\n已经成功处理的部分不会重复发布。要继续下一个账号吗？"
                                % (name, result.get("error")),
                            ):
                                break
                    done_items += len(videos)
                    self.set_progress(done_items, total_items)
                    wait_seconds = float(creator_cfg.get("inter_account_wait_seconds", 30))
                    if position < len(targets) - 1 and wait_seconds > 0 and not self.stop_event.is_set():
                        self.append_log("账号之间休息 %.0f 秒，然后切换下一个账号" % wait_seconds)
                        time.sleep(wait_seconds)
        except Exception as exc:
            self.append_log("运行中断：%s" % exc)
            self.append_log(traceback.format_exc())
        finally:
            try:
                report_path = write_report(
                    self.report_dir / ("运行结果_%s.xlsx" % date_str),
                    state.items(),
                )
                self.append_log("结果报表已生成：%s" % report_path)
            except Exception as exc:
                self.append_log("生成报表失败：%s" % exc)
            self.set_status("运行结束：" + state.summary())
            self.append_log("运行结束：" + state.summary())
            self._set_running(False)
            self._show_run_summary(state)

    def _run_parallel(self, mode: str, targets, max_workers: int) -> None:
        """并行模式：账号之间并行，每个账号内部仍然串行。"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        state = RunState.load(cfgmod.RUN_DIR, date_str)
        self.state = state
        total_items = sum(len(item[1]) for item in targets) or 1

        def worker(target):
            account, videos, copies = target[:3]
            name = account.get("name") or "未命名账号"
            settings = (
                list(target[3])
                if len(target) > 3
                else settings_for_videos(name, videos, self.publish_settings)
            )
            task_event = threading.Event()
            self.register_task(name, task_event, len(videos))
            bridge = TaskBridge(self, name, task_event)
            try:
                result = self._run_one_account(
                    mode,
                    account,
                    videos,
                    copies,
                    settings,
                    state,
                    bridge,
                    task_event=task_event,
                    confirm_plan=False,
                )
                if result.get("error"):
                    self.append_log("[%s] 任务结束但有异常：%s" % (name, result.get("error")))
                return result
            finally:
                self.unregister_task(name)

        try:
            results, errors = run_parallel_jobs(targets, worker, max_workers=max_workers)
            for item, exc in errors:
                name = (item[0].get("name") if isinstance(item, tuple) and item else "未知账号")
                self.append_log("并行任务「%s」异常：%s" % (name, exc))
        except Exception as exc:
            self.append_log("并行运行中断：%s" % exc)
            self.append_log(traceback.format_exc())
        finally:
            try:
                report_path = write_report(
                    self.report_dir / ("运行结果_%s.xlsx" % date_str),
                    state.items(),
                )
                self.append_log("结果报表已生成：%s" % report_path)
            except Exception as exc:
                self.append_log("生成报表失败：%s" % exc)
            self.set_status("运行结束：" + state.summary())
            self.append_log("运行结束：" + state.summary())
            self._set_running(False)
            self._show_run_summary(state)

    def _run_one_account(
        self,
        mode: str,
        account,
        videos,
        copies,
        target_settings,
        state,
        bridge,
        task_event=None,
        confirm_plan: bool = True,
    ):
        """一个账号的完整任务：上传发布、待办理记录、金牛改名。"""
        name = account.get("name") or "未命名账号"
        result = {
            "account": name,
            "published": 0,
            "skipped": 0,
            "skipped_videos": [],
            "scheduled": [],
            "dry_run": mode == "dry",
        }

        def is_stopped() -> bool:
            return bool(task_event is not None and task_event.is_set()) or self.stop_event.is_set()

        # 已记录为今天已发布的视频：由用户决定是否重发。
        if mode in ("dry", "publish"):
            already = [str(video) for video in videos if state.is_published_path(name, str(video))]
            if already:
                shown = "、".join(Path(item).name for item in already[:6])
                answer = bridge.rescue(
                    "有视频被记录为「今天已发布」",
                    "账号「%s」有 %d 条视频在今天的记录里是「已发布」：\n%s\n\n"
                    "如果它们其实没发出去（比如之前浏览器异常被误判），选第一项重新发布一遍。"
                    % (name, len(already), shown),
                    ["全部重新发布一遍", "按记录跳过这些", "停止运行"],
                )
                if answer == "停止运行":
                    return dict(result, stopped=True)
                if answer == "全部重新发布一遍":
                    removed = state.clear_paths(name, already)
                    self.append_log("[%s] 已清除 %d 条的「已发布」记录，这次会重新发布" % (name, removed))

        if mode in ("dry", "publish") and confirm_plan and self.confirm_run.get():
            if not bridge.plan_editor(account, videos, copies, mode="confirm"):
                self.append_log("你跳过了账号：%s" % name)
                return dict(result, skipped_account=True)
            target_settings = settings_for_videos(name, videos, self.publish_settings)

        setting_problems = []
        for item_index, setting in enumerate(target_settings, start=1):
            problem = validate_publish_at(
                setting.get("publish_at"),
                min_lead_minutes=int((self.cfg.get("creator") or {}).get("schedule_min_lead_minutes", 60)),
                max_days=int((self.cfg.get("creator") or {}).get("schedule_max_days", 14)),
            )
            if problem:
                setting_problems.append("第 %d 条：%s" % (item_index, problem))
        if setting_problems:
            message = "账号「%s」的发布设置没有通过：\n%s" % (name, "\n".join(setting_problems))
            self.append_log("[%s] %s" % (name, message))
            bridge.status("发布设置未通过，已跳过该账号")
            return dict(result, error="发布设置未通过")

        scheduled_present = has_scheduled(
            {setting_key(name, str(video)): setting for video, setting in zip(videos, target_settings)}
        )
        auto_rename_this = (
            mode == "rename"
            or (
                mode == "publish"
                and self.auto_rename.get()
                and not (
                    scheduled_present
                    and not bool((self.cfg.get("creator") or {}).get("auto_rename_when_scheduled", False))
                )
            )
        )
        if mode == "publish" and scheduled_present and not auto_rename_this:
            self.append_log("[%s] 包含定时发布，已跳过自动改名，写入待改金牛素材名台账。" % name)

        browser = None
        try:
            mode_for_browser = "jinniu" if mode == "rename" else "creator"
            browser = AccountBrowser(
                self.cfg,
                account,
                mode=mode_for_browser,
                logger=self.logger,
                progress=bridge.status,
                should_stop=is_stopped,
            )
            browser.start()
            self.active_browser = browser
            self.register_browser(name, browser)
            if mode in ("dry", "publish"):
                ctx = CreatorContext(
                    bridge,
                    browser.page,
                    self.cfg,
                    account,
                    videos,
                    copies,
                    state,
                    self.logger,
                    video_settings=target_settings,
                    dry_run=(mode == "dry"),
                )
                result = run_creator_account(ctx)
                if mode == "publish":
                    for scheduled in result.get("scheduled") or []:
                        self.pending.add(
                            name,
                            scheduled.get("file", ""),
                            scheduled.get("copy", ""),
                            scheduled.get("publish_at", ""),
                        )
                    if result.get("scheduled"):
                        self.append_log(
                            "[%s] 已记录 %d 条定时发布的待改金牛素材名。"
                            % (name, len(result.get("scheduled") or []))
                        )
                if mode == "publish" and not result.get("published"):
                    self.append_log("[%s] 本次没有新发布的作品，跳过金牛改名。" % name)
            if auto_rename_this:
                self.append_log("[%s] 进入金牛改名阶段。" % name)
                jctx = JinniuContext(
                    bridge,
                    browser.page,
                    self.cfg,
                    account,
                    videos,
                    copies,
                    state,
                    self.logger,
                )
                run_jinniu_account(jctx, after_publish=(mode == "publish"))
                renamed_files = [
                    str(item.get("file") or "")
                    for item in state.items()
                    if item.get("account") == name and item.get("rename_status") == "已改名"
                ]
                if renamed_files:
                    removed = self.pending.resolve(name, renamed_files)
                    if removed:
                        self.append_log("[%s] 已核销 %d 条待改金牛素材名台账。" % (name, removed))
        except Exception as exc:
            self.append_log("[%s] 账号中断：%s" % (name, exc))
            self.append_log(traceback.format_exc())
            if is_stopped() or isinstance(exc, StoppedByUser):
                return dict(result, stopped=True)
            return dict(result, error=str(exc))
        finally:
            self.unregister_browser(name)
            if self.active_browser is browser:
                self.active_browser = None
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
        return result

    def _show_run_summary(self, state) -> None:
        """跑完给一个明确的结论弹窗，避免用户不知道进度到哪了。"""
        items = state.items()
        if not items:
            return
        published = sum(1 for item in items if item.get("publish_status") == "已发布")
        scheduled = sum(
            1
            for item in items
            if item.get("publish_status") == "已发布" and item.get("publish_at")
        )
        skipped_video = sum(1 for item in items if item.get("publish_status") == "已跳过")
        renamed = sum(1 for item in items if item.get("rename_status") == "已改名")
        skipped = sum(1 for item in items if item.get("rename_status") == "已跳过")
        review = sum(1 for item in items if item.get("rename_status") == "待核对")
        failed = sum(
            1 for item in items if item.get("publish_status") in ("发布结果不确定", "失败")
        )
        problems = [
            item
            for item in items
            if item.get("note")
            or item.get("rename_status") in ("待核对", "已跳过")
            or item.get("publish_status") == "已跳过"
        ]
        lines = [
            "今日结果：",
            "· 已发布 %d 条" % published,
            "· 金牛已改名 %d 条" % renamed,
        ]
        if scheduled:
            lines.append("· 其中定时发布 %d 条（不自动改金牛素材名，已写入待办）" % scheduled)
        if skipped_video:
            lines.append("· 因发布设置未通过而跳过 %d 条" % skipped_video)
        if skipped:
            lines.append("· 改名跳过 %d 条" % skipped)
        if review:
            lines.append("· 待人工核对 %d 条" % review)
        if failed:
            lines.append("· 发布异常 %d 条" % failed)
        if problems:
            lines.append("")
            lines.append("需要你看一眼的明细（共 %d 条）：" % len(problems))
            for item in problems:
                lines.append(
                    "· %s：%s（%s）"
                    % (
                        item.get("account", ""),
                        item.get("file", "") or Path(str(item.get("path") or "")).name or ("第 %d 条" % (int(item.get("index", 0)) + 1)),
                        str(item.get("note") or item.get("publish_status") or item.get("rename_status"))[:40],
                    )
                )
            lines.append("")
            lines.append("完整结果在「打开报表」里的《运行结果_日期.xlsx》。")
        try:
            content = "\n".join(lines)
            try:
                self.root.deiconify()
                self.root.lift()
            except Exception:
                pass
            self.root.after(
                0,
                lambda: text_dialog(self.root, "本次运行结束", content, 900, 620, modal=False),
            )
            self.append_log("—— 本次运行结束 ——")
            self.append_log(content)
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno(
                "任务还在运行",
                "任务还在跑。确定要退出吗？重新打开工具可以从中断的地方继续。",
                parent=self.root,
            ):
                return
            self.stop_event.set()
        self.close_setup_browser()
        try:
            self.root.destroy()
        except Exception:
            pass
