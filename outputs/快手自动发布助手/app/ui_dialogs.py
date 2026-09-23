# -*- coding: utf-8 -*-
"""界面弹窗：对照表确认、人工接管、跨线程调用。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional, Sequence


class UiRequest:
    """把要在界面线程里执行的动作投递过去，并等待结果。"""

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.fn = fn
        self.event = threading.Event()
        self.result: Any = None

    def run(self) -> None:
        try:
            self.result = self.fn()
        except Exception:
            self.result = None
        finally:
            self.event.set()

    def wait(self, timeout: Optional[float] = None) -> Any:
        self.event.wait(timeout)
        return self.result


def center_on_parent(dialog, parent, width: int = 0, height: int = 0) -> None:
    """把弹窗摆在父窗口中间；父窗口不可用时摆屏幕中间，并保证不越出屏幕。"""
    try:
        dialog.update_idletasks()
    except Exception:
        pass
    w = width or dialog.winfo_width() or dialog.winfo_reqwidth()
    h = height or dialog.winfo_height() or dialog.winfo_reqheight()
    try:
        screen_w, screen_h = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    except Exception:
        screen_w, screen_h = 1920, 1080
    x = y = None
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        if pw > 1 and ph > 1:
            x = px + max((pw - w) // 2, 0)
            y = py + max((ph - h) // 3, 0)
    except Exception:
        pass
    if x is None:
        x = max((screen_w - w) // 2, 0)
        y = max((screen_h - h) // 2, 0)
    # 夹紧到屏幕内：避免多屏/缩放时被系统摆到屏幕左上角或越界
    x = min(max(x, 0), max(screen_w - w - 8, 0))
    y = min(max(y, 0), max(screen_h - h - 48, 0))
    dialog.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def recenter() -> None:
        """主窗口的位置可能要等一会儿才确定，稍后再校正一次。"""
        try:
            if not dialog.winfo_exists():
                return
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            if pw <= 1 or ph <= 1:
                return
            nx = px + max((pw - w) // 2, 0)
            ny = py + max((ph - h) // 3, 0)
            nx = min(max(nx, 0), max(screen_w - w - 8, 0))
            ny = min(max(ny, 0), max(screen_h - h - 48, 0))
            dialog.geometry("+%d+%d" % (nx, ny))
        except Exception:
            pass

    try:
        dialog.after(150, recenter)
    except Exception:
        pass


def bring_to_front(dialog, parent=None) -> None:
    """把弹窗抬到最前面，避免被浏览器窗口挡住后用户以为程序卡死。"""
    try:
        dialog.lift()
        dialog.attributes("-topmost", True)
        dialog.after(1500, lambda: dialog.attributes("-topmost", False))
    except Exception:
        pass
    try:
        dialog.focus_force()
    except Exception:
        pass


def text_dialog(parent, title: str, content: str, width: int = 900, height: int = 600, modal: bool = False) -> None:
    """可滚动、可缩放的文本弹窗（用于运行结果这类长内容）。

    modal=False（默认）时不会锁住主窗口——结果窗口必须是非模态的，否则用户会以为程序卡死。
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.minsize(600, 400)
    dialog.resizable(True, True)
    frame = ttk.Frame(dialog)
    frame.pack(fill="both", expand=True, padx=12, pady=(12, 6))
    text = tk.Text(frame, wrap="char", font=("Microsoft YaHei UI", 10), relief="solid", borderwidth=1)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    text.insert("1.0", content)
    text.configure(state="disabled")
    bar = ttk.Frame(dialog)
    bar.pack(fill="x", padx=12, pady=(0, 12))
    ttk.Button(bar, text="关闭", command=dialog.destroy).pack(side="right")
    ttk.Label(bar, text="内容较长时可以滚动查看，也可以拖动窗口右下角放大", font=("Microsoft YaHei UI", 9), foreground="#666666").pack(side="left")
    center_on_parent(dialog, parent, width, height)
    bring_to_front(dialog, parent)
    if modal:
        dialog.grab_set()
        dialog.wait_window()


def table_dialog(
    parent,
    title: str,
    message: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    confirm_text: str = "确认，按这个顺序执行",
    cancel_text: str = "取消该账号",
) -> bool:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.minsize(820, 480)
    dialog.resizable(True, True)
    dialog.geometry("1100x620")
    center_on_parent(dialog, parent, 1100, 620)
    bring_to_front(dialog, parent)
    ttk.Label(dialog, text=message, wraplength=1040, justify="left").pack(anchor="w", padx=12, pady=(12, 6))
    frame = ttk.Frame(dialog)
    frame.pack(fill="both", expand=True, padx=12, pady=4)
    tree = ttk.Treeview(frame, columns=list(headers), show="headings", height=18)
    for col in headers:
        tree.heading(col, text=col)
        width = 90 if col in ("序号", "状态") else 300
        tree.column(col, width=width, anchor="w")
    yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    for row in rows:
        tree.insert("", "end", values=list(row))
    state = {"ok": False}
    bar = ttk.Frame(dialog)
    bar.pack(fill="x", padx=12, pady=10)
    ttk.Button(bar, text=confirm_text, command=lambda: (state.update(ok=True), dialog.destroy())).pack(side="right", padx=4)
    if cancel_text:
        ttk.Button(bar, text=cancel_text, command=dialog.destroy).pack(side="right", padx=4)
    dialog.wait_window()
    return state["ok"]


def rescue_dialog(parent, title: str, message: str, options: Sequence[str]) -> str:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.geometry("680x280")
    center_on_parent(dialog, parent, 680, 280)
    bring_to_front(dialog, parent)
    ttk.Label(dialog, text=message, wraplength=640, justify="left").pack(anchor="w", padx=14, pady=(14, 8))
    result = {"value": options[-1] if options else ""}
    bar = ttk.Frame(dialog)
    bar.pack(fill="x", padx=14, pady=12)

    def make(value: str):
        def handler() -> None:
            result["value"] = value
            dialog.destroy()
        return handler

    for option in options:
        ttk.Button(bar, text=option, command=make(option)).pack(side="left", padx=4)
    dialog.wait_window()
    return result["value"]
