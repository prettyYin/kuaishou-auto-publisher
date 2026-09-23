# -*- coding: utf-8 -*-
"""首次使用向导：3 步把工具配好，账号数量可以自己加。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List

from . import config as cfgmod
from .loginconfig import (
    NEW_LOGIN_LABEL,
    apply_to_account,
    browser_by_label,
    browser_labels,
    default_browser_label,
    login_label,
    login_options,
)
from .ui_dialogs import center_on_parent

TITLE_FONT = ("Microsoft YaHei UI", 12, "bold")
LABEL_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)
STEP_TITLES = [
    "第 1 步 / 共 3 步：账号、浏览器和登录方式",
    "第 2 步 / 共 3 步：两个平台的网址",
    "第 3 步 / 共 3 步：每个账号的素材文件夹",
]


class SetupWizard(tk.Toplevel):
    def __init__(self, app) -> None:
        super().__init__(app.root)
        self.app = app
        self.title("第一次使用：3 步设置")
        self.geometry("1040x640")
        center_on_parent(self, app.root, 1040, 640)
        self.minsize(900, 560)
        self.transient(app.root)
        self.grab_set()
        self.step = 0
        self.browsers = browser_by_label()
        self.account_vars: List[Dict[str, Any]] = []
        self.publish_url = tk.StringVar()
        self.jinniu_url = tk.StringVar()
        self.order_var = tk.StringVar(value="最新上传的排在最上面")

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(14, 4))
        self.step_label = ttk.Label(header, text=STEP_TITLES[0], font=TITLE_FONT)
        self.step_label.pack(anchor="w")
        ttk.Label(
            header,
            text="这一步只做一次，配好以后每天回「今天要发的」页签点开始就行。中途可以点「稍后再设置」。",
            font=SMALL_FONT,
            foreground="#666666",
        ).pack(anchor="w", pady=(2, 0))

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=16, pady=8)
        self.frames = [self._build_step_accounts(), self._build_step_urls(), self._build_step_folders()]

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=16, pady=(4, 14))
        ttk.Button(footer, text="稍后再设置", command=self.destroy).pack(side="left")
        self.finish_button = ttk.Button(footer, text="完成", command=self.finish)
        self.finish_button.pack(side="right", padx=4)
        self.next_button = ttk.Button(footer, text="下一步", command=self.next_step)
        self.next_button.pack(side="right", padx=4)
        self.prev_button = ttk.Button(footer, text="上一步", command=self.prev_step)
        self.prev_button.pack(side="right", padx=4)

        self._fill_from_config()
        self._show_step(0)

    # ---------- 第 1 步：账号 ----------
    def _build_step_accounts(self) -> ttk.Frame:
        frame = ttk.Frame(self.body)
        ttk.Label(
            frame,
            text="你有几个账号就加几行。浏览器可以选 Chrome / Edge 等；登录方式建议用「新建：首次扫码登录」，"
            "这样不用动你现在正在用的浏览器。",
            font=LABEL_FONT,
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))
        detected = [item for item in self.browsers.values() if item.get("exe")]
        if detected:
            text = "这台电脑上检测到：" + "、".join(item["name"] for item in detected)
        else:
            text = "没有自动检测到浏览器，请先安装 Chrome 或 Edge。"
        ttk.Label(frame, text=text, font=SMALL_FONT, foreground="#0b5cad", wraplength=980, justify="left").pack(anchor="w", pady=(0, 8))
        self.accounts_box = ttk.LabelFrame(frame, text=" 账号列表 ")
        self.accounts_box.pack(fill="both", expand=True)
        self.rows_holder = ttk.Frame(self.accounts_box)
        self.rows_holder.pack(fill="x")
        ttk.Button(self.accounts_box, text="＋ 添加账号", command=lambda: self._add_account_row()).pack(anchor="w", padx=8, pady=6)
        return frame

    def _add_account_row(self, account: Dict[str, Any] = None) -> None:
        account = account or {}
        row = ttk.Frame(self.rows_holder)
        row.pack(fill="x", padx=8, pady=5)
        enabled = tk.BooleanVar(value=bool(account.get("enabled")))
        name = tk.StringVar(value=account.get("name") or "")
        browser_label = account.get("browser_name") or default_browser_label()
        if browser_label not in self.browsers:
            browser_label = default_browser_label()
        browser_var = tk.StringVar(value=browser_label)
        profile = account.get("browser_source_profile") or ""
        options = login_options(browser_label, profile, self.browsers)
        current = next((item for item in options if profile and item.endswith("（%s）" % profile)), NEW_LOGIN_LABEL)
        login_var = tk.StringVar(value=current)
        login_combo = ttk.Combobox(row, textvariable=login_var, values=options, state="readonly", width=34)
        browser_combo = ttk.Combobox(row, textvariable=browser_var, values=browser_labels(), state="readonly", width=16)

        def refresh_login(*_args) -> None:
            values = login_options(browser_var.get(), "", self.browsers)
            login_combo.configure(values=values)
            if login_var.get() not in values:
                login_var.set(NEW_LOGIN_LABEL)

        browser_combo.bind("<<ComboboxSelected>>", refresh_login)
        ttk.Checkbutton(row, text="要用", variable=enabled).pack(side="left")
        ttk.Label(row, text="账号名 *", font=LABEL_FONT).pack(side="left", padx=(10, 4))
        name_entry = ttk.Entry(row, textvariable=name, width=14, font=LABEL_FONT)
        name_entry.pack(side="left")
        ttk.Label(row, text="浏览器", font=LABEL_FONT).pack(side="left", padx=(10, 4))
        browser_combo.pack(side="left")
        ttk.Label(row, text="登录方式", font=LABEL_FONT).pack(side="left", padx=(10, 4))
        login_combo.pack(side="left")
        ttk.Label(row, text="金牛账户ID *", font=LABEL_FONT).pack(side="left", padx=(10, 4))
        account_id = tk.StringVar(value=str(account.get("jinniu_account_id") or ""))
        ttk.Entry(row, textvariable=account_id, width=13, font=SMALL_FONT).pack(side="left")
        item = {
            "frame": row,
            "enabled": enabled,
            "name": name,
            "browser": browser_var,
            "login": login_var,
            "login_combo": login_combo,
            "account_id": account_id,
        }
        self.account_vars.append(item)
        ttk.Button(row, text="删除", width=6, command=lambda: self.delete_account_row(item)).pack(side="left", padx=(10, 0))
        name_entry.bind("<KeyRelease>", lambda event: self._rebuild_folder_rows())
        enabled.trace_add("write", lambda *args: self._rebuild_folder_rows())
        self._rebuild_folder_rows()

    def delete_account_row(self, item: Dict[str, Any]) -> None:
        index = next((i for i, existing in enumerate(self.account_vars) if existing is item), None)
        if index is None:
            return
        name = item["name"].get().strip() or "这个账号"
        if not messagebox.askyesno("删除账号", "确定要删除「%s」吗？" % name, parent=self):
            return
        self.account_vars.pop(index)
        try:
            item["frame"].destroy()
        except Exception:
            pass
        self._rebuild_folder_rows()

    # ---------- 第 2 步：网址 ----------
    def _build_step_urls(self) -> ttk.Frame:
        frame = ttk.Frame(self.body)
        ttk.Label(
            frame,
            text="把下面两个页面的网址粘贴进来（在浏览器里打开那个页面，复制地址栏里的内容即可）。",
            font=LABEL_FONT,
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        box = ttk.LabelFrame(frame, text=" 平台地址 ")
        box.pack(fill="x")
        row1 = ttk.Frame(box)
        row1.pack(fill="x", padx=8, pady=6)
        ttk.Label(row1, text="创作者平台「发布作品 / 上传视频」页", font=LABEL_FONT, width=32).pack(side="left")
        ttk.Entry(row1, textvariable=self.publish_url, font=SMALL_FONT).pack(side="left", fill="x", expand=True)
        row2 = ttk.Frame(box)
        row2.pack(fill="x", padx=8, pady=6)
        ttk.Label(row2, text="磁力金牛「视频库 / 素材库」页", font=LABEL_FONT, width=32).pack(side="left")
        ttk.Entry(row2, textvariable=self.jinniu_url, font=SMALL_FONT).pack(side="left", fill="x", expand=True)
        row3 = ttk.Frame(box)
        row3.pack(fill="x", padx=8, pady=(6, 10))
        ttk.Label(row3, text="金牛素材列表顺序", font=LABEL_FONT, width=32).pack(side="left")
        ttk.Combobox(
            row3,
            textvariable=self.order_var,
            values=["最新上传的排在最上面", "最早上传的排在最上面"],
            state="readonly",
            width=26,
        ).pack(side="left")
        ttk.Label(row3, text="（金牛默认最新在最上面，改名时按这个换算顺序）", font=SMALL_FONT, foreground="#888888").pack(side="left", padx=8)
        return frame

    # ---------- 第 3 步：素材文件夹 ----------
    def _build_step_folders(self) -> ttk.Frame:
        frame = ttk.Frame(self.body)
        ttk.Label(
            frame,
            text="每个账号当天要发的视频放在哪个文件夹？文件夹里视频的顺序（按文件名）就是发布顺序。",
            font=LABEL_FONT,
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        box = ttk.LabelFrame(frame, text=" 素材文件夹 ")
        box.pack(fill="both", expand=True)
        self.folder_holder = ttk.Frame(box)
        self.folder_holder.pack(fill="x")
        ttk.Label(
            frame,
            text="提示：只有勾了「要用」的账号才需要选文件夹。",
            font=SMALL_FONT,
            foreground="#666666",
        ).pack(anchor="w", pady=(8, 0))
        return frame

    def _rebuild_folder_rows(self) -> None:
        if not hasattr(self, "folder_holder"):
            return
        for widget in self.folder_holder.winfo_children():
            widget.destroy()
        for index, item in enumerate(self.account_vars):
            row = ttk.Frame(self.folder_holder)
            row.pack(fill="x", padx=8, pady=5)
            name = item["name"].get().strip() or ("账号 %d" % (index + 1))
            label = ttk.Label(row, text=name, font=LABEL_FONT, width=18)
            label.pack(side="left")
            var = item.setdefault("folder", tk.StringVar(value=""))
            ttk.Entry(row, textvariable=var, font=SMALL_FONT).pack(side="left", fill="x", expand=True, padx=6)
            ttk.Button(row, text="选择文件夹", width=11, command=lambda v=var, i=index: self.choose_folder(v, i)).pack(side="left")
            if item["enabled"].get():
                if var.get().strip():
                    ttk.Label(row, text="＊必填（已填）", font=SMALL_FONT, foreground="#1a7f37").pack(side="left", padx=4)
                else:
                    ttk.Label(row, text="＊必填", font=SMALL_FONT, foreground="#b3261e").pack(side="left", padx=4)
            else:
                ttk.Label(row, text="（未勾选「要用」，可不填）", font=SMALL_FONT, foreground="#888888").pack(side="left", padx=4)

    # ---------- 交互 ----------
    def _fill_from_config(self) -> None:
        cfg = self.app.cfg
        creator = cfg.get("creator", {})
        jinniu = cfg.get("jinniu", {})
        self.publish_url.set(creator.get("publish_url") or "")
        self.jinniu_url.set(jinniu.get("video_library_url") or "")
        self.order_var.set(
            "最早上传的排在最上面" if (jinniu.get("list_order") or "newest_first") == "oldest_first" else "最新上传的排在最上面"
        )
        accounts = cfg.get("accounts", [])
        for account in accounts:
            self._add_account_row(account)
            self.account_vars[-1]["folder"].set(account.get("video_dir") or "")
        if not accounts:
            self._add_account_row()

    def choose_folder(self, var: tk.StringVar, index: int) -> None:
        name = self.account_vars[index]["name"].get().strip() or ("账号 %d" % (index + 1))
        folder = filedialog.askdirectory(parent=self, title="选择「%s」的素材文件夹" % name)
        if folder:
            var.set(folder)

    def _show_step(self, step: int) -> None:
        for frame in self.frames:
            frame.pack_forget()
        self.frames[step].pack(fill="both", expand=True)
        self.step = step
        self.step_label.configure(text=STEP_TITLES[step])
        self.prev_button.configure(state="normal" if step > 0 else "disabled")
        self.next_button.configure(state="normal" if step < len(self.frames) - 1 else "disabled")
        self.finish_button.configure(state="normal" if step == len(self.frames) - 1 else "disabled")
        if step == 2:
            self._rebuild_folder_rows()

    def next_step(self) -> None:
        if self.step < len(self.frames) - 1:
            self._show_step(self.step + 1)

    def prev_step(self) -> None:
        if self.step > 0:
            self._show_step(self.step - 1)

    def finish(self) -> None:
        missing_folder = [
            (row["name"].get().strip() or ("账号 %d" % (index + 1)))
            for index, row in enumerate(self.account_vars)
            if row["enabled"].get() and not (row.get("folder") and row["folder"].get().strip())
        ]
        missing_name = [
            ("第 %d 行" % (index + 1))
            for index, row in enumerate(self.account_vars)
            if row["enabled"].get() and not row["name"].get().strip()
        ]
        missing_id = [
            (row["name"].get().strip() or ("第 %d 行" % (index + 1)))
            for index, row in enumerate(self.account_vars)
            if row["enabled"].get() and not row["account_id"].get().strip()
        ]
        if missing_name or missing_id:
            lines = []
            if missing_name:
                lines.append("· 没填账号名：%s" % "、".join(missing_name))
            if missing_id:
                lines.append(
                    "· 没填金牛账户ID：%s\n  （在浏览器里打开该账号的磁力金牛「视频库」，地址栏里 __accountId__= 后面那串数字就是；\n"
                    "   也可以先留空跳过，之后在「设置 → 打开浏览器检查登录」打开金牛素材库，工具会自动识别并填上）"
                    % "、".join(missing_id)
                )
            messagebox.showwarning(
                "还有必填项没填",
                "这些是必填项：\n\n%s\n\n请回到第 1 步补上（不需要的账号可以取消勾选「要用」）。" % "\n\n".join(lines),
                parent=self,
            )
            self._show_step(0)
            return
        if missing_folder:
            messagebox.showwarning(
                "还差素材文件夹",
                "这些账号勾了「要用」但还没有选素材文件夹：\n\n%s\n\n请在第 3 步补上（不需要的账号可以取消勾选「要用」）。"
                % "、".join(missing_folder),
                parent=self,
            )
            self._show_step(2)
            return
        cfg = self.app.cfg
        accounts: List[Dict[str, Any]] = []
        enabled_names = []
        for index, row in enumerate(self.account_vars):
            account = cfgmod.default_account(index)
            account["enabled"] = bool(row["enabled"].get())
            account["name"] = row["name"].get().strip() or cfgmod.default_account(index)["name"]
            account["video_dir"] = row["folder"].get().strip() if row.get("folder") else ""
            account["jinniu_account_id"] = row["account_id"].get().strip() if row.get("account_id") else ""
            apply_to_account(account, row["browser"].get(), row["login"].get(), self.browsers)
            accounts.append(account)
            if account["enabled"]:
                enabled_names.append(account["name"])
        cfg["accounts"] = accounts
        creator = cfg.setdefault("creator", {})
        creator["publish_url"] = self.publish_url.get().strip()
        jinniu = cfg.setdefault("jinniu", {})
        jinniu["video_library_url"] = self.jinniu_url.get().strip()
        jinniu["list_order"] = "oldest_first" if self.order_var.get().startswith("最早") else "newest_first"
        self.app.save_config()
        self.app.reload_from_config()
        self.destroy()
        if enabled_names:
            messagebox.showinfo(
                "设置完成",
                "已经配好 %d 个账号：%s\n\n下一步：到「设置」页点「打开浏览器检查登录」，"
                "要登录就扫码一次；然后用「仅演练（不发布）」试跑一遍。"
                % (len(enabled_names), "、".join(enabled_names)),
                parent=self.app.root,
            )
        else:
            messagebox.showinfo("设置已保存", "还没有勾选要用的账号，随时可以在「设置」页继续配置。", parent=self.app.root)
