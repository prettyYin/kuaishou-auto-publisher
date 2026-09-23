# -*- coding: utf-8 -*-
"""启动辅助：首次通过 exe 启动时创建桌面快捷方式。"""
from __future__ import annotations

import os
import base64
import subprocess
from pathlib import Path

from . import config as cfgmod

CREATE_NO_WINDOW = 0x08000000


def _ps_quote(value: str) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def ensure_desktop_shortcut(logger=None) -> str:
    """只在通过启动器 exe 运行时执行；失败不影响主程序。"""
    if os.environ.get("KUAISHOU_AUTO_LAUNCHER") != "1":
        return ""
    exe = os.environ.get("KUAISHOU_AUTO_EXE") or ""
    if not exe or not Path(exe).exists():
        return ""
    marker = cfgmod.RUN_DIR / ".shortcut_created"
    if marker.exists():
        return str(marker)
    workdir = str(Path(exe).resolve().parent)
    script = (
        "$desktop=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop '快手自动发布助手.lnk'));"
        "$s.TargetPath=%s;"
        "$s.WorkingDirectory=%s;"
        "$s.Description='快手自动发布助手';"
        "$s.Save();"
    ) % (_ps_quote(exe), _ps_quote(workdir))
    try:
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if completed.returncode != 0:
            if logger:
                try:
                    logger.warning(
                        "创建桌面快捷方式失败（不影响使用）：%s",
                        (completed.stderr or completed.stdout or "PowerShell 返回非零").strip(),
                    )
                except Exception:
                    pass
            return ""
        cfgmod.RUN_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text("created", encoding="utf-8")
    except Exception as exc:
        if logger:
            try:
                logger.warning("创建桌面快捷方式失败（不影响使用）：%s", exc)
            except Exception:
                pass
    return str(marker)
