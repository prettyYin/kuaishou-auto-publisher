# -*- coding: utf-8 -*-
"""读勘查快照，输出页面结构和关键元素（供补选择器用）。"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手\logs\recon")


def main() -> None:
    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            print("=" * 78)
            print("目录:", folder.name)
            print("标题:", data.get("title"))
            print("网址:", data.get("url"))
            elements = data.get("elements") or []
            rows = data.get("rows") or []
            dialogs = data.get("dialogs") or []
            print("元素 %d 个 / 表格行 %d 行 / 弹窗 %d 个" % (len(elements), len(rows), len(dialogs)))
            print("--- 输入类控件 ---")
            for el in elements:
                if el.get("tag") in ("input", "textarea") or el.get("tag") == "div":
                    print("  <%s type=%s ph=%r aria=%r id=%r cls=%r text=%r>" % (
                        el.get("tag"), el.get("type"), (el.get("placeholder") or "")[:24],
                        (el.get("aria") or "")[:20], (el.get("id") or "")[:24],
                        (el.get("cls") or "")[:48], (el.get("text") or "")[:30]))
            print("--- 按钮/链接（有文字的） ---")
            for el in elements:
                if el.get("tag") in ("button", "a") and (el.get("text") or "").strip():
                    print("  <%s cls=%r text=%r>" % (el.get("tag"), (el.get("cls") or "")[:40], (el.get("text") or "")[:30]))
            if rows:
                print("--- 表格前几行 ---")
                for row in rows[:3]:
                    print("  行文字:", row.get("text", "")[:150])
            if dialogs:
                print("--- 弹窗 ---")
                for item in dialogs[:2]:
                    print("  cls=%r" % (item.get("cls") or "")[:80])
                    print("  文字:", (item.get("text") or "")[:200])


if __name__ == "__main__":
    main()
