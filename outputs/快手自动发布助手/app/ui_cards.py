# -*- coding: utf-8 -*-
"""账号卡片（紧凑列表版）：一眼看清状态，一键粘贴广告语。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List

from .copytext import parse_copies

TITLE_FONT = ("Microsoft YaHei UI", 11, "bold")
LABEL_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)
BIG_FONT = ("Microsoft YaHei UI", 11, "bold")

GREEN = "#1a7f37"
ORANGE = "#b35c00"
RED = "#b3261e"
GRAY = "#666666"


def status_for(enabled: bool, video_count: int, copy_count: int, folder: str) -> tuple:
    """返回 (提示文字, 颜色)。"""
    if not enabled:
        return "未启用（勾选左边「今天要发这个账号」才会参与）", GRAY
    if not folder:
        return "第一步：点「选择文件夹」指定今天放视频的地方", ORANGE
    if video_count == 0:
        return "这个文件夹里没有视频文件，请把视频放进去再点「重新扫描」", ORANGE
    if copy_count == 0:
        return "有 %d 个视频：点「粘贴广告语」把 %d 条广告语粘进去" % (video_count, video_count), ORANGE
    if copy_count != video_count:
        return "数量不一样：视频 %d 个 / 广告语 %d 条，请核对后重新粘贴" % (video_count, copy_count), RED
    return "已配对：%d 个视频 / %d 条广告语，可以开跑" % (video_count, copy_count), GREEN


class AccountCard:
    def __init__(self, parent: tk.Widget, index: int, app) -> None:
        self.index = index
        self.app = app
        self.frame = ttk.LabelFrame(parent, text=" 账号 %d " % (index + 1))
        self.frame.pack(fill="x", padx=8, pady=4)
        self.enabled = tk.BooleanVar(value=False)
        self.name_var = tk.StringVar()
        self.dir_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self.count_var = tk.StringVar(value="")
        self.task_status_var = tk.StringVar(value="")
        self.task_progress_var = tk.StringVar(value="")
        self._videos: List = []
        self.raw_text = ""
        self.strip_index = False
        self.batch = False

        first = ttk.Frame(self.frame)
        first.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Checkbutton(first, text="今天要发这个账号", variable=self.enabled, command=self.app.refresh_all).pack(side="left")
        ttk.Label(first, text="账号名字", font=LABEL_FONT).pack(side="left", padx=(14, 4))
        self.name_display = ttk.Label(first, textvariable=self.name_var, font=LABEL_FONT, foreground="#1a1e2a")
        self.name_display.pack(side="left")
        ttk.Label(first, text="（在设置页修改）", font=SMALL_FONT, foreground="#888888").pack(side="left", padx=(2, 0))
        ttk.Label(first, text="素材文件夹", font=LABEL_FONT).pack(side="left", padx=(14, 4))
        ttk.Entry(first, textvariable=self.dir_var, font=SMALL_FONT).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(first, text="选择文件夹", width=11, command=self.choose_dir).pack(side="left", padx=2)
        ttk.Button(first, text="打开", width=6, command=self.open_dir).pack(side="left", padx=2)
        ttk.Button(first, text="重新扫描", width=9, command=self.app.refresh_all).pack(side="left", padx=2)

        second = ttk.Frame(self.frame)
        second.pack(fill="x", padx=8, pady=(2, 8))
        self.status_label = ttk.Label(second, textvariable=self.status_var, font=BIG_FONT)
        self.status_label.pack(side="left")
        ttk.Label(second, textvariable=self.count_var, font=SMALL_FONT, foreground=GRAY).pack(side="left", padx=10)
        self.stop_button = ttk.Button(second, text="停止该账号", width=11, command=self.stop_task, state="disabled")
        self.stop_button.pack(side="right", padx=2)
        ttk.Button(second, text="查看对照表", width=12, command=self.preview).pack(side="right", padx=2)
        self.copy_button = ttk.Button(second, text="粘贴广告语", width=12, command=self.open_copy_dialog)
        self.copy_button.pack(side="right", padx=2)

        third = ttk.Frame(self.frame)
        third.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(third, textvariable=self.task_status_var, font=SMALL_FONT, foreground="#0b5cad").pack(side="left")
        ttk.Label(third, textvariable=self.task_progress_var, font=SMALL_FONT, foreground=GRAY).pack(side="left", padx=10)

    # ---------- 交互 ----------
    def choose_dir(self) -> None:
        folder = filedialog.askdirectory(parent=self.app.root, title="选择「%s」今天放视频的文件夹" % (self.name_var.get() or "账号"))
        if folder:
            self.dir_var.set(folder)
            self.app.refresh_all()

    def open_dir(self) -> None:
        folder = self.dir_var.get().strip()
        if not folder:
            messagebox.showinfo("还没有选文件夹", "请先点「选择文件夹」。", parent=self.app.root)
            return
        self.app.open_dir(folder)

    def open_copy_dialog(self) -> None:
        from .ui_copydialog import CopyDialog

        CopyDialog(self.app, self)

    def preview(self) -> None:
        self.app.preview_account(self)

    def stop_task(self) -> None:
        self.app.stop_account(self.name_var.get().strip())

    def set_task_state(self, status: str = "", progress: str = "") -> None:
        self.task_status_var.set(status or "")
        self.task_progress_var.set(progress or "")

    def set_task_active(self, active: bool) -> None:
        try:
            self.stop_button.configure(state="normal" if active else "disabled")
        except Exception:
            pass

    # ---------- 数据 ----------
    def set_copies(self, raw: str, strip_index: bool = False, batch: bool = False) -> None:
        self.raw_text = raw or ""
        self.strip_index = bool(strip_index)
        # 本工具固定为"这一批视频共用同一条广告语"
        self.batch = True

    def copies(self, count: int = None) -> List[str]:
        """本工具的规则：这一批视频共用同一条广告语。"""
        text = self.raw_text.strip()
        if not text:
            return []
        total = count if count is not None else len(self._videos)
        return [text] * max(int(total), 0)

    def clear_copies(self) -> None:
        self.set_copies("", False, False)
        self.app.save_copies(self)
        self.app.refresh_all()

    def refresh(self) -> None:
        self._videos, copies = self.app.account_plan(self)
        text, color = status_for(self.enabled.get(), len(self._videos), len(copies), self.dir_var.get().strip())
        if self.batch and self.enabled.get() and self._videos and len(copies) == len(self._videos):
            text = "已配对：%d 个视频 · 全部使用同一条广告语" % len(self._videos)
            color = GREEN
        self.status_var.set(text)
        self.status_label.configure(foreground=color)
        total = 0
        for video in self._videos:
            try:
                total += video.stat().st_size
            except OSError:
                pass
        if self._videos:
            self.count_var.set("%d 个视频 · %s" % (len(self._videos), self.app.human_size(total)))
        else:
            self.count_var.set("")

    @property
    def videos(self):
        return self._videos

    def set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for parent in (self.frame,):
            for child in parent.winfo_children():
                for widget in child.winfo_children():
                    try:
                        if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Checkbutton)):
                            widget.configure(state=state)
                    except Exception:
                        pass
        try:
            if not running:
                self.stop_button.configure(state="disabled")
        except Exception:
            pass
