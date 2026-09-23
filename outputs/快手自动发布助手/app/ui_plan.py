# -*- coding: utf-8 -*-
"""对照表编辑器：左侧看顺序，右侧逐条设置作者声明和发布时间。"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Sequence

from .publish_settings import (
    AUTHOR_DECLARATION_OPTIONS,
    AUTHOR_NONE_LABEL,
    PREVIEW_COLUMNS,
    default_schedule_time,
    format_publish_at,
    normalize_publish_at,
    parse_publish_at,
    summarize_author,
    validate_publish_at,
)
from .ui_dialogs import bring_to_front, center_on_parent

TITLE_FONT = ("Microsoft YaHei UI", 12, "bold")
LABEL_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)


class PlanEditorDialog:
    """对照表编辑器。

    mode="preview"：从主界面点「查看对照表」打开，只编辑，不启动发布。
    mode="confirm"：上传前确认时打开，确认后按当前设置执行。
    """

    def __init__(
        self,
        parent,
        account_name: str,
        videos: Sequence[Any],
        copies: Sequence[str],
        get_settings: Callable[[str], Dict[str, Any]],
        save_settings: Callable[[int, str, Dict[str, Any]], None],
        creator_cfg: Optional[Dict[str, Any]] = None,
        mode: str = "preview",
    ) -> None:
        self.parent = parent
        self.account_name = account_name or "未命名账号"
        self.videos = list(videos or [])
        self.copies = list(copies or [])
        self.get_settings = get_settings
        self.save_settings = save_settings
        self.creator_cfg = creator_cfg or {}
        self.mode = "confirm" if mode == "confirm" else "preview"

        self.result = False
        self._loading = False
        self._current = 0
        self._more_open = False
        self._rows: List[Dict[str, Any]] = []
        self._default_time = self._next_round_time()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(
            ("发布前确认 · %s" if self.mode == "confirm" else "对照表预览 · %s") % self.account_name
        )
        self.dialog.transient(parent)
        self.dialog.minsize(1080, 640)
        self.dialog.geometry("1220x760")
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        center_on_parent(self.dialog, parent, 1220, 760)
        bring_to_front(self.dialog, parent)
        self._build()
        self._refresh_table()
        if self._rows:
            self._select_index(0)

    # ---------- 时间辅助 ----------
    @staticmethod
    def _next_round_time() -> datetime:
        return default_schedule_time()

    def _build(self) -> None:
        ttk.Label(
            self.dialog,
            text="对照表 · %s" % self.account_name,
            font=TITLE_FONT,
        ).pack(anchor="w", padx=16, pady=(14, 4))
        ttk.Label(
            self.dialog,
            text="左侧是发布顺序，右侧是选中视频的设置。作者声明默认「不设置」，发布时间默认「立即发布」。",
            font=LABEL_FONT,
        ).pack(anchor="w", padx=16)
        ttk.Label(
            self.dialog,
            text="提醒：作者声明只在本次打开工具期间有效；如果中断重开，未发布视频会按空声明继续。"
            "定时时间会保存在当天进度里。",
            font=SMALL_FONT,
            foreground="#b35c00",
            wraplength=1160,
        ).pack(anchor="w", padx=16, pady=(4, 8))

        body = ttk.Panedwindow(self.dialog, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        self._build_table(left)
        self._build_settings(right)

        bar = ttk.Frame(self.dialog)
        bar.pack(fill="x", padx=16, pady=(2, 12))
        self.validation_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.validation_var, foreground="#b3261e", font=SMALL_FONT).pack(
            side="left"
        )
        if self.mode == "confirm":
            ttk.Button(bar, text="跳过这个账号", command=self._cancel).pack(side="right", padx=4)
            ttk.Button(
                bar,
                text="确认，按这个设置执行",
                style="Go.TButton",
                command=self._confirm,
            ).pack(side="right", padx=4)
        else:
            ttk.Button(bar, text="关闭", command=self._confirm).pack(side="right", padx=4)

    def _build_table(self, parent) -> None:
        box = ttk.LabelFrame(parent, text=" 发布顺序 ")
        box.pack(fill="both", expand=True, padx=(0, 6))
        holder = ttk.Frame(box)
        holder.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree = ttk.Treeview(
            holder,
            columns=PREVIEW_COLUMNS,
            show="headings",
            selectmode="extended",
            height=22,
        )
        widths = {
            "序号": 54,
            "文件名": 290,
            "广告语": 300,
            "作者声明": 120,
            "发布时间": 150,
            "状态": 160,
        }
        for col in PREVIEW_COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths.get(col, 120), minwidth=50, stretch=False, anchor="w")
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree.tag_configure("bad", foreground="#b3261e")
        self.tree.tag_configure("ok", foreground="#1a7f37")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_settings(self, parent) -> None:
        box = ttk.LabelFrame(parent, text=" 本条设置 ")
        box.pack(fill="both", expand=True)

        self.detail_var = tk.StringVar(value="请先选择左侧的一条视频")
        ttk.Label(
            box,
            textvariable=self.detail_var,
            font=LABEL_FONT,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 6))

        common = ttk.LabelFrame(box, text=" 常用设置 ")
        common.pack(fill="x", padx=10, pady=6)

        author_row = ttk.Frame(common)
        author_row.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(author_row, text="作者声明", font=LABEL_FONT, width=10).pack(side="left")
        self.author_var = tk.StringVar(value=AUTHOR_NONE_LABEL)
        self.author_combo = ttk.Combobox(
            author_row,
            textvariable=self.author_var,
            values=[AUTHOR_NONE_LABEL] + list(AUTHOR_DECLARATION_OPTIONS),
            state="readonly",
            width=28,
        )
        self.author_combo.pack(side="left", fill="x", expand=True)
        self.author_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._apply_indices([self._current], quiet=True),
        )
        ttk.Label(
            common,
            text="不设置就是空。\n选不上时工具会重试 2 次；仍失败就跳过这一条，不会带着错误声明发布。",
            font=SMALL_FONT,
            foreground="#777777",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        schedule_box = ttk.LabelFrame(common, text=" 发布时间 ")
        schedule_box.pack(fill="x", padx=8, pady=(2, 8))
        self.schedule_mode = tk.StringVar(value="immediate")
        row = ttk.Frame(schedule_box)
        row.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Radiobutton(
            row,
            text="立即发布",
            variable=self.schedule_mode,
            value="immediate",
            command=self._schedule_changed,
        ).pack(side="left")
        ttk.Radiobutton(
            row,
            text="定时发布",
            variable=self.schedule_mode,
            value="scheduled",
            command=self._schedule_changed,
        ).pack(side="left", padx=12)

        self.time_row = ttk.Frame(schedule_box)
        self.time_row.pack(fill="x", padx=8, pady=(2, 8))
        now = self._default_time
        self.year_var = tk.StringVar(value=str(now.year))
        self.month_var = tk.StringVar(value="%02d" % now.month)
        self.day_var = tk.StringVar(value="%02d" % now.day)
        self.hour_var = tk.StringVar(value="%02d" % now.hour)
        self.minute_var = tk.StringVar(value="%02d" % now.minute)
        spin_specs = (
            ("年", self.year_var, now.year, now.year + 1, 5),
            ("月", self.month_var, 1, 12, 3),
            ("日", self.day_var, 1, 31, 3),
            ("时", self.hour_var, 0, 23, 3),
            ("分", self.minute_var, 0, 59, 3),
        )
        self.time_spins = []
        for label, var, start, end, width in spin_specs:
            ttk.Label(self.time_row, text=label, font=SMALL_FONT).pack(side="left", padx=(0 if label == "年" else 4, 1))
            spin = ttk.Spinbox(
                self.time_row,
                from_=start,
                to=end,
                width=width,
                textvariable=var,
                command=self._schedule_changed,
            )
            spin.pack(side="left")
            spin.bind("<FocusOut>", lambda _event: self._schedule_changed())
            spin.bind("<Return>", lambda _event: self._schedule_changed())
            self.time_spins.append(spin)
        ttk.Label(
            schedule_box,
            text="平台规则：定时发布只支持未来 1 小时到 %d 天内。\n"
            "默认值：当前时间 61 分钟后。\n"
            "提交前会用鼠标在页面日期面板中选择，并回读校验。"
            % int(self.creator_cfg.get("schedule_max_days", 14)),
            font=SMALL_FONT,
            foreground="#777777",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        more = ttk.Frame(box)
        more.pack(fill="x", padx=10, pady=(4, 0))
        self.more_button = ttk.Button(more, text="展开更多设置 ▸", command=self._toggle_more)
        self.more_button.pack(anchor="w")
        self.more_frame = ttk.LabelFrame(box, text=" 更多设置 ")
        ttk.Label(
            self.more_frame,
            text="关联热点 / 添加地点 / 作者服务：已经预留位置，后续接入时不会增加左侧表格列数。",
            font=SMALL_FONT,
            foreground="#777777",
            wraplength=410,
            justify="left",
        ).pack(anchor="w", padx=8, pady=8)

        actions = ttk.Frame(box)
        actions.pack(fill="x", padx=10, pady=10)
        ttk.Button(actions, text="应用本条", command=lambda: self._apply_indices([self._current])).pack(
            side="left", padx=2
        )
        ttk.Button(
            actions,
            text="套用到选中行",
            command=lambda: self._apply_indices(self._selected_indices() or list(range(len(self._rows)))),
        ).pack(side="left", padx=2)
        ttk.Button(
            actions,
            text="套用到全部",
            command=lambda: self._apply_indices(list(range(len(self._rows)))),
        ).pack(side="left", padx=2)
        ttk.Button(actions, text="本条恢复立即发布", command=self._make_immediate).pack(
            side="left", padx=2
        )

    # ---------- 数据 ----------
    def _settings(self, index: int) -> Dict[str, Any]:
        row = self._rows[index]
        return dict(self.get_settings(row["path"]) or {})

    def _refresh_table(self, keep_selection: bool = True) -> None:
        selected = self._selected_indices() if keep_selection else []
        self.tree.delete(*self.tree.get_children())
        self._rows = []
        for index, video in enumerate(self.videos):
            path = str(video)
            file_name = getattr(video, "name", None) or Path(path).name
            copy_text = self.copies[index] if index < len(self.copies) else ""
            setting = dict(self.get_settings(path) or {})
            error = self._validate_setting(setting)
            item_id = self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index + 1,
                    file_name,
                    copy_text,
                    summarize_author(setting.get("author_statement")),
                    format_publish_at(setting.get("publish_at")),
                    ("待修改：%s" % error) if error else "就绪",
                ),
                tags=("bad" if error else "ok",),
            )
            self._rows_append(index, path, file_name, copy_text, item_id)
        if keep_selection and selected:
            for index in selected:
                if 0 <= index < len(self._rows):
                    self.tree.selection_add(str(index))
        if self._rows and not self.tree.selection():
            self._select_index(min(self._current, len(self._rows) - 1))

    def _rows_append(self, index, path, file_name, copy_text, item_id) -> None:
        while len(self._rows) <= index:
            self._rows.append({})
        self._rows[index] = {
            "index": index,
            "path": path,
            "file": file_name,
            "copy": copy_text,
            "iid": item_id,
        }

    def _select_index(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        self.tree.selection_set(str(index))
        self.tree.focus(str(index))
        self.tree.see(str(index))
        self._load_controls(index)

    def _selected_indices(self) -> List[int]:
        result: List[int] = []
        for item in self.tree.selection():
            try:
                result.append(int(item))
            except Exception:
                pass
        return sorted(set(result))

    def _on_select(self, _event=None) -> None:
        selected = self._selected_indices()
        if not selected:
            return
        self._current = selected[0]
        self._load_controls(self._current)

    def _load_controls(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        row = self._rows[index]
        setting = self._settings(index)
        self._loading = True
        try:
            author = str(setting.get("author_statement") or "")
            self.author_var.set(author if author in AUTHOR_DECLARATION_OPTIONS else AUTHOR_NONE_LABEL)
            publish_at = str(setting.get("publish_at") or "")
            parsed = parse_publish_at(publish_at)
            if parsed is None:
                self.schedule_mode.set("immediate")
                parsed = self._default_time
            else:
                self.schedule_mode.set("scheduled")
            self.year_var.set(str(parsed.year))
            self.month_var.set("%02d" % parsed.month)
            self.day_var.set("%02d" % parsed.day)
            self.hour_var.set("%02d" % parsed.hour)
            self.minute_var.set("%02d" % parsed.minute)
            self.detail_var.set(
                "第 %d 条：%s\n\n广告语：\n%s"
                % (index + 1, row.get("file") or "", row.get("copy") or "（还没有广告语）")
            )
            self._sync_time_state()
        finally:
            self._loading = False
        self._set_validation("")

    def _sync_time_state(self) -> None:
        state = "normal" if self.schedule_mode.get() == "scheduled" else "disabled"
        for spin in getattr(self, "time_spins", []):
            try:
                spin.configure(state=state)
            except Exception:
                pass

    def _toggle_more(self) -> None:
        self._more_open = not self._more_open
        if self._more_open:
            self.more_frame.pack(fill="x", padx=10, pady=(4, 0), after=self.more_button.master)
            self.more_button.configure(text="收起更多设置 ▾")
        else:
            self.more_frame.pack_forget()
            self.more_button.configure(text="展开更多设置 ▸")

    def _controls_value(self):
        author = self.author_var.get().strip()
        if author == AUTHOR_NONE_LABEL:
            author = ""
        if self.schedule_mode.get() == "scheduled":
            try:
                dt = datetime(
                    int(self.year_var.get()),
                    int(self.month_var.get()),
                    int(self.day_var.get()),
                    int(self.hour_var.get()),
                    int(self.minute_var.get()),
                )
            except Exception:
                return None, "定时时间不完整或格式不对"
            publish_at = dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            publish_at = ""
        return {"author_statement": author, "publish_at": publish_at}, ""

    def _validate_setting(self, setting: Dict[str, Any]) -> str:
        return validate_publish_at(
            setting.get("publish_at"),
            min_lead_minutes=int(self.creator_cfg.get("schedule_min_lead_minutes", 60)),
            max_days=int(self.creator_cfg.get("schedule_max_days", 14)),
        )

    def _schedule_changed(self) -> None:
        if self._loading:
            return
        self._sync_time_state()
        if self.schedule_mode.get() == "immediate":
            self._set_validation("")
            self._apply_indices([self._current], quiet=True)
            return
        value, error = self._controls_value()
        if error:
            self._set_validation(error)
            return
        problem = self._validate_setting(value or {})
        self._set_validation(problem)
        if not problem:
            self._apply_indices([self._current], quiet=True)

    def _make_immediate(self) -> None:
        self._loading = True
        try:
            self.schedule_mode.set("immediate")
            self._sync_time_state()
        finally:
            self._loading = False
        self._apply_indices([self._current])

    def _apply_indices(self, indices: Sequence[int], quiet: bool = False) -> bool:
        if not indices:
            return False
        value, error = self._controls_value()
        if error:
            self._set_validation(error)
            if not quiet:
                messagebox.showwarning("设置不完整", error, parent=self.dialog)
            return False
        problem = self._validate_setting(value or {})
        if problem:
            self._set_validation(problem)
            if not quiet:
                messagebox.showwarning("定时时间不符合要求", problem, parent=self.dialog)
            return False
        for index in indices:
            if not (0 <= index < len(self._rows)):
                continue
            row = self._rows[index]
            self.save_settings(index, row["path"], dict(value or {}))
        self._set_validation("")
        self._refresh_table(keep_selection=True)
        self._select_index(self._current)
        return True

    def _validate_all(self) -> bool:
        errors = []
        for index in range(len(self._rows)):
            problem = self._validate_setting(self._settings(index))
            if problem:
                errors.append("第 %d 条：%s" % (index + 1, problem))
        if errors:
            text = "有 %d 条设置需要修改：\n\n%s" % (len(errors), "\n".join(errors[:8]))
            self._set_validation(errors[0])
            messagebox.showwarning("还不能开始", text, parent=self.dialog)
            return False
        return True

    def _set_validation(self, text: str) -> None:
        try:
            self.validation_var.set(text or "")
        except Exception:
            pass

    def _confirm(self) -> None:
        if self.mode == "confirm" and not self._validate_all():
            return
        self.result = True
        self.dialog.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.dialog.destroy()

    def show(self) -> bool:
        try:
            self.dialog.grab_set()
        except Exception:
            pass
        self.dialog.wait_window()
        return bool(self.result)
