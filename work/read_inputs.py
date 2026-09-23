# -*- coding: utf-8 -*-
"""看最新快照里的所有输入框和弹窗文字（找搜索框与改名弹窗）。"""
from __future__ import annotations

import json
import pathlib
import sys


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    folders = sorted([f for f in root.iterdir() if f.is_dir()], key=lambda f: f.stat().st_mtime, reverse=True)
    for folder in folders[:3]:
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            print("=" * 76)
            print(folder.name, "|", data.get("title"), "|", (data.get("url") or "")[:70])
            for el in data.get("elements") or []:
                if el.get("tag") in ("input", "textarea") or "search" in (el.get("cls") or "").lower():
                    print("  <%s type=%-8s ph=%r aria=%r id=%r cls=%r text=%r>" % (
                        el.get("tag"), el.get("type"), (el.get("placeholder") or "")[:26],
                        (el.get("aria") or "")[:18], (el.get("id") or "")[:20],
                        (el.get("cls") or "")[:44], (el.get("text") or "")[:26]))
            for dialog in data.get("dialogs") or []:
                print("  --- 弹窗 cls=%r ---" % (dialog.get("cls") or "")[:60])
                print("     文字:", (dialog.get("text") or "")[:220])


if __name__ == "__main__":
    main()
