# -*- coding: utf-8 -*-
"""渲染主界面并截图，用于检查排版（临时脚本，放在 work/ 下）。"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

TOOL = Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")
WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\work")
SHOTS = WORK / "ui-shots"
DEMO = WORK / "demo-videos"
sys.path.insert(0, str(TOOL))

from win_grab import grab_hwnd


def shot(window, name):
    window.lift()
    window.attributes("-topmost", True)
    window.update()
    time.sleep(0.9)
    SHOTS.mkdir(parents=True, exist_ok=True)
    target = SHOTS / (name + ".png")
    image = grab_hwnd(int(window.frame(), 16))
    image.save(target)
    print("saved", target)


def make_demo_videos():
    for account, count in (("A", 4), ("B", 2)):
        folder = DEMO / account
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(1, count + 1):
            target = folder / ("睫毛膏素材%d.mp4" % index)
            if not target.exists():
                target.write_bytes(b"0" * 1024)
    return DEMO / "A", DEMO / "B"


def main():
    cfg_path = TOOL / "config" / "config.json"
    backup = cfg_path.read_text(encoding="utf-8")
    folder_a, folder_b = make_demo_videos()
    app = None
    try:
        from app.ui import AutoApp
        from app.ui_wizard import SetupWizard

        app = AutoApp()
        app._maybe_first_run = lambda: None
        app.cfg["creator"]["publish_url"] = "https://cp.kuaishou.com/article/publish/video"
        app.cfg["creator"]["works_url"] = "https://cp.kuaishou.com/article/manage/video"
        app.cfg["jinniu"]["video_library_url"] = "https://niu.kuaishou.com/creative/material/video"

        app.cards[0].enabled.set(True)
        app.cards[0].name_var.set("账号A（示例）")
        app.cards[0].dir_var.set(str(folder_a))
        app.cards[0].set_copies("睫毛膏浓密卷翘不晕染\n刷头细好上手\n防水不脱妆\n新手也能画出太阳花")

        app.cards[1].enabled.set(True)
        app.cards[1].name_var.set("账号B（示例）")
        app.cards[1].dir_var.set(str(folder_b))

        app.cards[2].name_var.set("账号C（示例）")
        app.cards[3].name_var.set("账号D（示例）")
        app.cards[2].dir_var.set(str(folder_b))
        app.cards[3].dir_var.set(str(folder_a))

        app.root.geometry("1280x900+30+20")
        app.refresh_all()
        app.set_progress(7, 24)
        app.set_status("【账号A（示例）】第 4/12 条：睫毛膏素材4.mp4")
        app.append_log("演示：已上传 3 条，正在处理第 4 条")

        shot(app.root, "1-今天要发的")
        from app.ui_copydialog import CopyDialog

        dialog = CopyDialog(app, app.cards[0])
        dialog.geometry("920x680+80+60")
        shot(dialog, "5-粘贴广告语")
        dialog.geometry("820x460+120+120")
        shot(dialog, "6-粘贴广告语-小窗口")
        dialog.destroy()
        app.notebook.select(app.tab_settings)
        app.settings_tab.busy_var.set("浏览器已打开（账号：账号A（示例））。当前页面：https://cp.kuaishou.com/article/publish/video")
        shot(app.root, "2-设置")
        app.notebook.select(app.tab_help)
        shot(app.root, "3-使用帮助")
        app.notebook.select(app.tab_today)
        wizard = SetupWizard(app)
        wizard.geometry("980x620+60+40")
        shot(wizard, "4-引导设置")
        wizard.next_step()
        wizard.next_step()
        shot(wizard, "7-引导设置-文件夹必填")
        wizard.destroy()
    finally:
        cfg_path.write_text(backup, encoding="utf-8")
        if app is not None:
            try:
                app.root.destroy()
            except Exception:
                pass
    print("done")


if __name__ == "__main__":
    main()
