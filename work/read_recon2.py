# -*- coding: utf-8 -*-
"""深入看金牛页面：素材名元素、改名入口、弹窗内容。"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手\logs\recon")


def main() -> None:
    for folder in sorted(ROOT.iterdir()):
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            url = data.get("url") or ""
            if "niu.e.kuaishou" not in url:
                continue
            elements = data.get("elements") or []
            print("=" * 78)
            print(url)
            print("元素总数:", len(elements))
            print("--- 全部元素（按位置 y 排序，只显示有文字或关键 class 的） ---")
            for el in sorted(elements, key=lambda item: (item.get("y") or 0, item.get("x") or 0)):
                text = (el.get("text") or "").strip()
                cls = el.get("cls") or ""
                if not text and not any(key in cls.lower() for key in ("name", "title", "material", "photo", "card", "item", "table")):
                    continue
                print("  y=%-5s x=%-5s <%s type=%s cls=%r text=%r ph=%r>" % (
                    el.get("y"), el.get("x"), el.get("tag"), el.get("type"),
                    cls[:60], text[:50], (el.get("placeholder") or "")[:24]))
            for dialog in data.get("dialogs") or []:
                print("--- 弹窗 cls=%r ---" % (dialog.get("cls") or "")[:80])
                print("   文字:", (dialog.get("text") or "")[:300])
                print("   HTML:", (dialog.get("html") or "")[:600])


if __name__ == "__main__":
    main()
