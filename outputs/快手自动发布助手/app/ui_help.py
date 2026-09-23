# -*- coding: utf-8 -*-
"""帮助页签：使用说明 + 一键诊断。"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Dict, List

from . import config as cfgmod

TITLE_FONT = ("Microsoft YaHei UI", 11, "bold")
LABEL_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)

HELP_TEXT = """【这个工具帮你做什么】

每天你只要做三件事：
  1. 把当天的视频放进各个账号的「素材文件夹」；
  2. 把广告语复制好，在账号卡片里点「从剪贴板粘贴」；
  3. 在「查看对照表」里按需选择作者声明、发布时间，然后点「开始上传发布」。

接下来的事情脚本会自己做：
  · 在快手创作者服务平台，一条一条上传视频、把标题填成对应广告语、点发布；
  · 上一条发布成功后等 15 秒，再做下一条，保证发布顺序和你的对照表一致；
  · 一个账号全部跑完，才切换到下一个账号；
  · 最后到磁力金牛，把当天新增素材的素材名改回对应的视频文件名（方便统计小组业绩）。

如果不想一个账号等完再跑下一个账号，可以点「▶ 同步开始上传发布」：
  · 多个账号同时运行，但每个账号内部仍然逐条上传、逐条发布，顺序不会乱；
  · 默认同时 2 个账号，可以改成 1-5；
  · 某个账号失败或手动停止时，只停该账号，其他账号继续。

工具不会做：新建投放计划、选素材投放、出价、删除作品、改作品可见性。

【每天的顺序怎么决定】

顺序 = 素材文件夹里按文件名排序的结果（视频1 → 视频2 → 视频10），
广告语按你粘贴的行顺序一一对应。所以如果顺序不对，检查文件名即可。

【安全机制】

  · 作者声明：逐条选择、默认不设置；选不上会重试 2 次，仍失败就跳过这一条，不会带着错误声明发布；
  · 定时发布：逐条设置；只要本账号有定时发布，就不会自动改金牛素材名，待办会在下次打开时提醒；
  · 发布前确认：每个账号开跑前会弹出对照表，你看一眼再确认；
  · 演练模式：先点「仅演练（不发布）」，只走到填标题、不点发布；
  · 不跳步：某一条结果不确定（超时、页面变了、网络断了），会立刻停下等你处理，
    绝不会跳过它继续做下一条（跳过会让后面全部错位）；
  · 断点续跑：已经发布成功的条目会记下来，重新运行不会重复发布；
  · 异常即停：登录失效、出现验证码、页面结构变化都会停下并截图。

【常见问题】

Q：弹出「需要你手动…」的提示怎么办？
A：说明脚本没认出页面上某个元素。照着提示在浏览器窗口里手动做一步，再选对应选项继续。
   同时把 logs/shots 里最新的截图发给我，我会修正页面规则。

Q：提示登录失效？
A：在那个自动化浏览器窗口里扫码登录，然后重新启动该账号，脚本会从断点继续。

Q：为什么这么慢？
A：单条视频 300MB 以上，又要串行 + 每条间隔 10 秒，耗时主要由上传带宽决定。
   建议晚上开跑、早上看报表；也可以分批，比如上午 3 个账号、下午 2 个账号。
   运行期间工具会自动阻止电脑休眠，但请不要关机。

Q：想调整速度或条数上限？
A：到「设置」页签改：每条发布后等待秒数、账号之间休息秒数、当日条数上限。

Q：只想改金牛素材名 / 这次不想改名？
A：点「只改金牛素材名」按钮；或取消勾选主界面的「上传发布完成后自动执行金牛改名」。

【出问题时怎么求助】

点下面的「复制诊断信息」，然后把内容粘贴发给我（里面只有配置和日志，没有账号密码）。
如果方便，再把 logs/shots 里对应时间的截图一起发来。
"""


def build_help_tab(parent, app) -> "HelpTab":
    return HelpTab(parent, app)


class HelpTab:
    def __init__(self, parent: tk.Widget, app) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(bar, text="使用说明与问题排查", font=TITLE_FONT).pack(side="left")
        ttk.Button(bar, text="📋 复制诊断信息", command=self.copy_diagnostics).pack(side="right", padx=4)
        ttk.Button(bar, text="打开日志目录", command=lambda: app.open_dir(cfgmod.LOG_DIR)).pack(side="right", padx=4)
        ttk.Button(bar, text="打开报表目录", command=lambda: self.open_reports()).pack(side="right", padx=4)
        ttk.Button(bar, text="打开使用说明文档", command=self.open_readme).pack(side="right", padx=4)

        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        text = tk.Text(holder, wrap="word", font=LABEL_FONT, relief="solid", borderwidth=1)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", HELP_TEXT)
        text.configure(state="disabled")
        self.text = text

    def open_readme(self) -> None:
        path = cfgmod.BASE_DIR / "README_使用说明.md"
        try:
            import os

            os.startfile(str(path))
        except Exception:
            messagebox.showinfo("使用说明", "文件位置：\n%s" % path, parent=self.app.root)

    def open_reports(self) -> None:
        self.app.open_dir(self.app.report_dir)

    def diagnostics(self) -> str:
        cfg = self.app.cfg
        lines: List[str] = []
        lines.append("=== 快手自动发布助手 诊断信息 ===")
        lines.append("时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("工具目录：%s" % cfgmod.BASE_DIR)
        lines.append("创作者发布页：%s" % (cfg.get("creator", {}).get("publish_url") or "(未填写)"))
        lines.append("金牛视频库：%s" % (cfg.get("jinniu", {}).get("video_library_url") or "(未填写)"))
        lines.append("金牛列表顺序：%s" % cfg.get("jinniu", {}).get("list_order"))
        creator = cfg.get("creator", {})
        lines.append(
            "节奏：每条发布后 %s 秒 / 账号之间 %s 秒 / 当日上限 %s 条"
            % (creator.get("post_publish_wait_seconds"), creator.get("inter_account_wait_seconds"), creator.get("daily_total_limit"))
        )
        lines.append("")
        lines.append("--- 账号设置 ---")
        for index, account in enumerate(cfg.get("accounts", []), start=1):
            lines.append(
                "%d) %s | 启用=%s | Chrome配置=%s | 素材目录=%s | 自动化副本=%s"
                % (
                    index,
                    account.get("name"),
                    "是" if account.get("enabled") else "否",
                    "%s / %s" % (account.get("browser_name") or "自动", account.get("browser_source_profile") or "新建扫码登录"),
                    account.get("video_dir") or "(未填)",
                    cfgmod.account_auto_dir(cfg, account),
                )
            )
        lines.append("")
        lines.append("--- 今日进度 ---")
        try:
            lines.append(self.app.state.summary())
        except Exception:
            lines.append("(读取失败)")
        lines.append("")
        lines.append("--- 最近日志 ---")
        lines.append(self.app.recent_log_text(80))
        return "\n".join(lines)

    def copy_diagnostics(self) -> None:
        content = self.diagnostics()
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(content)
            messagebox.showinfo("已复制", "诊断信息已复制到剪贴板，直接粘贴发给我即可。", parent=self.app.root)
        except Exception as exc:
            messagebox.showwarning("复制失败", str(exc), parent=self.app.root)
