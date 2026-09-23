# -*- coding: utf-8 -*-
"""流程与界面之间的通信接口。"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional, Sequence

from .config import SHOT_DIR


def safe_name(text: str) -> str:
    return "".join(ch if ch not in r'\/:*?"<>|' else "_" for ch in str(text))


class Bridge:
    """流程运行期间需要的回调。界面层实现这些方法，命令行用下面这个简单实现。"""

    def log(self, message: str, *args) -> None:
        raise NotImplementedError

    def status(self, text: str) -> None:
        pass

    def progress(self, done: int, total: int) -> None:
        pass

    def stopped(self) -> bool:
        return False

    def confirm(self, title: str, message: str) -> bool:
        raise NotImplementedError

    def confirm_table(self, title: str, message: str, headers, rows) -> bool:
        return self.confirm(title, message)

    def rescue(self, title: str, message: str, options: Sequence[str]) -> str:
        """返回 options 里用户选中的那一项。"""
        raise NotImplementedError

    def shot(self, page, name: str) -> str:
        """页面截图，返回文件路径（失败返回空字符串）。"""
        return ""


class ConsoleBridge(Bridge):
    """命令行/勘查脚本使用：日志直接打印，确认走控制台输入。"""

    def __init__(self, printer: Optional[Callable[[str], None]] = None) -> None:
        self.printer = printer or print

    def log(self, message: str, *args) -> None:
        self.printer(message % args if args else message)

    def status(self, text: str) -> None:
        self.printer("[状态] %s" % text)

    def confirm(self, title: str, message: str) -> bool:
        self.printer("\n=== %s ===\n%s" % (title, message))
        answer = input("确认继续？(y/N) ").strip().lower()
        return answer in ("y", "yes", "是", "1")

    def confirm_table(self, title, message, headers, rows) -> bool:
        lines = [message, "", " | ".join(str(h) for h in headers)]
        for row in rows:
            lines.append(" | ".join(str(cell) for cell in row))
        return self.confirm(title, "\n".join(lines))

    def rescue(self, title: str, message: str, options: Sequence[str]) -> str:
        self.printer("\n=== %s ===\n%s" % (title, message))
        for index, option in enumerate(options, start=1):
            self.printer("  %d) %s" % (index, option))
        answer = input("请选择编号：").strip()
        try:
            return options[int(answer) - 1]
        except Exception:
            return options[-1]

    def shot(self, page, name: str) -> str:
        try:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            target = SHOT_DIR / ("%s_%s.png" % (datetime.now().strftime("%H%M%S"), safe_name(name)))
            page.screenshot(path=str(target), full_page=False)
            return str(target)
        except Exception:
            return ""
