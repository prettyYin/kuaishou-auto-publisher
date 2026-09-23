# -*- coding: utf-8 -*-
"""把 flow_jinniu.py 里所有 ctx.state.mark(_account_name(ctx), ...) 换成带路径的 mark_state(ctx, ...)。"""
from __future__ import annotations

import pathlib
import re

TOOL = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")
PATH = TOOL / "app" / "flow_jinniu.py"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    before = text.count("ctx.state.mark(")
    text = text.replace("ctx.state.mark(_account_name(ctx), ", "mark_state(ctx, ")
    text = re.sub(
        r"ctx\.state\.mark\(\s*\n(\s*)_account_name\(ctx\),\s*\n(\s*)",
        lambda match: "mark_state(ctx,\n%s%s" % (match.group(1), match.group(2)),
        text,
    )
    PATH.write_text(text, encoding="utf-8")
    print("替换前:", before, "剩余 ctx.state.mark(:", text.count("ctx.state.mark("))


if __name__ == "__main__":
    main()
