# -*- coding: utf-8 -*-
"""设置广告语弹窗：这一批视频共用同一条广告语（改名时靠它去金牛搜索素材）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import List

from .copytext import parse_copies
from .ui_cards import GRAY, GREEN, LABEL_FONT, ORANGE, SMALL_FONT, TITLE_FONT
from .ui_dialogs import center_on_parent


class CopyDialog(tk.Toplevel):
    def __init__(self, app, card) -> None:
        super().__init__(app.root)
        self.app = app
        self.card = card
        name = card.name_var.get().strip() or "账号 %d" % (card.index + 1)
        self.title("设置广告语 · %s" % name)
        self.geometry("880x620")
        center_on_parent(self, app.root, 880, 620)
        self.transient(app.root)
        self.grab_set()
        self.minsize(760, 520)

        videos = list(card.videos)
        folder = card.dir_var.get().strip()
        ttk.Label(self, text="设置广告语 · %s" % name, font=TITLE_FONT).pack(anchor="w", padx=16, pady=(14, 2))
        tip = (
            "这个账号有 %d 个视频，它们都会使用下面这同一条广告语作为作品标题。" % len(videos)
            if videos
            else "这个账号的素材文件夹里还没有视频，请先放视频并点「重新扫描」。"
        )
        ttk.Label(self, text=tip, font=LABEL_FONT, foreground="#0b5cad", wraplength=820, justify="left").pack(
            anchor="w", padx=16
        )
        if folder:
            ttk.Label(
                self, text="素材文件夹：%s" % folder, font=SMALL_FONT, foreground=GRAY, wraplength=820, justify="left"
            ).pack(anchor="w", padx=16, pady=(2, 0))

        # ---- 底部按钮 ----
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", padx=16, pady=(8, 14))
        ttk.Button(bar, text="保存并关闭", command=self.save).pack(side="right", padx=4)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="right", padx=4)
        ttk.Label(
            bar, text="保存后回主界面点「开始上传发布」即可", font=SMALL_FONT, foreground=GRAY
        ).pack(side="left")

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, font=LABEL_FONT).pack(side="bottom", anchor="w", padx=16)

        tools = ttk.Frame(self)
        tools.pack(side="bottom", fill="x", padx=16, pady=(6, 0))
        ttk.Button(tools, text="从剪贴板粘贴", command=self.paste_clipboard).pack(side="left")
        ttk.Button(tools, text="清空", command=self.clear).pack(side="left", padx=6)
        self.count_var = tk.StringVar(value="")
        ttk.Label(tools, textvariable=self.count_var, font=SMALL_FONT, foreground=GRAY).pack(side="left", padx=10)

        # ---- 唯一性提示 ----
        warn = tk.Frame(self, background="#fff8e6", highlightthickness=1, highlightbackground="#f2a93b")
        warn.pack(side="bottom", fill="x", padx=16, pady=(10, 0))
        tk.Label(
            warn,
            text="⚠ 广告语必须独一无二",
            font=("Microsoft YaHei UI", 10, "bold"),
            background="#fff8e6",
            fg="#b35c00",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(
            warn,
            text="改素材名时，工具是拿这条广告语去磁力金牛里搜索素材的。\n"
            "如果和同事用了同一句（或很像的）广告语，就可能把别人上传的素材改名，请务必确认这句广告语是你这批视频独有的。",
            font=SMALL_FONT,
            background="#fff8e6",
            fg="#8a5a00",
            justify="left",
            anchor="w",
            wraplength=800,
        ).pack(fill="x", padx=10, pady=(2, 8))

        # ---- 输入区 ----
        box = ttk.LabelFrame(self, text=" 广告语（这一批视频共用这一条） ")
        box.pack(side="bottom", fill="both", expand=True, padx=16, pady=(6, 0))
        self.text = tk.Text(box, height=4, wrap="word", font=LABEL_FONT, relief="solid", borderwidth=1)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8, padx=(0, 8))
        self.text.insert("1.0", card.raw_text.strip())
        self.text.bind("<KeyRelease>", lambda event: self.update_status())
        self.update_status()

    # ---------- 逻辑 ----------
    def value(self) -> str:
        """只取第一行非空内容（防止粘贴了一列广告语）。"""
        raw = self.text.get("1.0", "end")
        parsed = parse_copies(raw, drop_headers=True)
        return parsed[0].strip() if parsed else ""

    def update_status(self) -> None:
        value = self.value()
        lines = [line for line in self.text.get("1.0", "end").splitlines() if line.strip()]
        video_count = len(self.card.videos)
        folder = self.card.dir_var.get().strip()
        self.count_var.set("已填 %d 字" % len(value))
        if len(lines) > 1:
            self.count_var.set("已填 %d 字（只取第一行）" % len(value))
        if not folder:
            text, color = "还没有选择素材文件夹", ORANGE
        elif video_count == 0:
            text, color = "素材文件夹里没有视频文件", ORANGE
        elif not value:
            text, color = "请输入这一批视频共用的广告语", ORANGE
        else:
            text, color = "已设置：%d 个视频共用这 %d 个字的广告语，可以保存" % (video_count, len(value)), GREEN
        self.status_var.set(text)

    def paste_clipboard(self) -> None:
        try:
            content = self.app.root.clipboard_get()
        except Exception:
            messagebox.showwarning(
                "剪贴板是空的",
                "请先在表格或文档里选中广告语，按 Ctrl+C 复制，再点这个按钮。",
                parent=self,
            )
            return
        parsed = parse_copies(content, drop_headers=True)
        first = parsed[0].strip() if parsed else ""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", first)
        if len(parsed) > 1:
            messagebox.showinfo(
                "只取第一条",
                "你粘贴的内容有 %d 行，本工具的规则是「这一批视频共用同一条广告语」，所以只取第一行：\n\n%s"
                % (len(parsed), first[:60]),
                parent=self,
            )
        self.update_status()

    def clear(self) -> None:
        self.text.delete("1.0", "end")
        self.update_status()

    def save(self) -> None:
        value = self.value()
        if not value:
            messagebox.showwarning("还差一步", "请输入这一批视频共用的广告语。", parent=self)
            return
        if not messagebox.askyesno(
            "确认广告语唯一",
            "改素材名时会用这条广告语去金牛里搜索素材。\n\n"
            "请确认这句广告语是你这批视频独有的、没有和同事重复。\n\n"
            "广告语：\n%s\n\n确认无误并保存吗？" % value[:120],
            parent=self,
        ):
            return
        self.card.set_copies(value, False, True)
        self.app.save_copies(self.card)
        self.app.refresh_all()
        self.destroy()
