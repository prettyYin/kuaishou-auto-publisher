# -*- coding: utf-8 -*-
"""实测每个弹窗的落点：主窗口放到已知位置，再依次打开各类弹窗，打印它们的坐标。"""
from __future__ import annotations

import sys
from pathlib import Path

TOOL = Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")
sys.path.insert(0, str(TOOL))

from app import ui_dialogs  # noqa: E402

RECORDS = []
original_center = ui_dialogs.center_on_parent


def patched_center(dialog, parent, width=0, height=0):
    original_center(dialog, parent, width, height)
    try:
        dialog.update_idletasks()
        RECORDS.append(
            {
                "title": dialog.title(),
                "x": dialog.winfo_rootx(),
                "y": dialog.winfo_rooty(),
                "w": dialog.winfo_width(),
                "h": dialog.winfo_height(),
            }
        )
    except Exception as exc:
        RECORDS.append({"title": dialog.title(), "error": str(exc)})
    # 让模态弹窗自动关闭，避免阻塞
    dialog.after(250, dialog.destroy)


ui_dialogs.center_on_parent = patched_center


def main() -> None:
    from app.ui import AutoApp
    from app.ui_copydialog import CopyDialog
    from app.ui_wizard import SetupWizard

    app = AutoApp()
    app._maybe_first_run = lambda: None
    app.root.geometry("1100x820+400+150")
    app.root.update()
    root_x, root_y = app.root.winfo_rootx(), app.root.winfo_rooty()
    root_w, root_h = app.root.winfo_width(), app.root.winfo_height()
    print("主窗口位置: x=%d y=%d 宽=%d 高=%d" % (root_x, root_y, root_w, root_h))

    ui_dialogs.table_dialog(app.root, "对照表", "测试", ["A", "B"], [["1", "2"]])
    app.root.update()
    ui_dialogs.rescue_dialog(app.root, "提示", "测试", ["好"])
    app.root.update()
    ui_dialogs.text_dialog(app.root, "运行结果", "内容", 700, 400)
    app.root.update()
    CopyDialog(app, app.cards[0])
    app.root.update()
    SetupWizard(app)
    app.root.update()

    print("--- 弹窗实际位置 ---")
    for item in RECORDS:
        if "error" in item:
            print("  %s → 读取失败: %s" % (item["title"], item["error"]))
            continue
        inner_x = item["x"] - root_x
        inner_y = item["y"] - root_y
        inside = 0 <= inner_x <= root_w - 60 and 0 <= inner_y <= root_h - 60
        print(
            "  %-12s x=%-6d y=%-6d (相对主窗口 %+d, %+d) %s"
            % (item["title"], item["x"], item["y"], inner_x, inner_y, "在主窗口内 ✓" if inside else "★不在主窗口内")
        )
    app.root.destroy()


if __name__ == "__main__":
    main()
