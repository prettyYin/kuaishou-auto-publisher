# -*- coding: utf-8 -*-
"""程序入口：启动图形界面。"""
from __future__ import annotations

import os
import socket
import sys
import threading
import traceback
from pathlib import Path


_LOCK_PORT = 47653
_lock_socket = None


def _already_running() -> bool:
    """用本地端口做单实例锁：已经在跑的话就不再开第二个窗口。"""
    global _lock_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", _LOCK_PORT))
        sock.listen(1)
        _lock_socket = sock
        return False
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return True


def _show_message(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        # 放一个居中的小窗口当父窗口，让系统提示框显示在屏幕中间而不是左上角
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry("1x1+%d+%d" % (max(screen_w // 2, 0), max(screen_h // 2, 0)))
        root.update_idletasks()
        messagebox.showinfo(title, message, parent=root)
        root.destroy()
    except Exception:
        print("%s: %s" % (title, message))


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    os.chdir(str(base))
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    if _already_running():
        _show_message(
            "程序已经在运行",
            "「快手自动发布助手」已经打开了。\n\n请到任务栏（或按 Alt+Tab）找到它的窗口。\n"
            "如果确实找不到窗口，可以先把任务栏里的旧窗口关掉，再重新双击启动。",
        )
        return 0
    try:
        from app.startup import ensure_desktop_shortcut

        threading.Thread(target=ensure_desktop_shortcut, daemon=True).start()
    except Exception:
        pass
    try:
        from app.ui import AutoApp

        AutoApp().run()
    except Exception:
        detail = traceback.format_exc()
        crash_log = base / "启动失败.txt"
        try:
            crash_log.write_text(detail, encoding="utf-8")
        except Exception:
            pass
        _show_message(
            "启动失败",
            "程序启动时出错了，详细信息已写入：\n%s\n\n请把这个文件发给管理员。" % crash_log,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
