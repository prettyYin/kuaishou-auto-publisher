# -*- coding: utf-8 -*-
"""生成 CRLF 换行、带日志的 .bat 启动器（临时脚本）。"""
from __future__ import annotations

import pathlib

TOOL = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")

HEADER = """@echo off
chcp 65001 >nul
pushd "%~dp0"
setlocal
set "LOGFILE=%~dp0启动日志.txt"
echo ===== {title} %date% %time% ===== >> "%LOGFILE%"

set "PYEXE="
set "PYARGS="
if exist "F:\\MySofeware\\dev_tools\\Python\\Python39\\python.exe" set "PYEXE=F:\\MySofeware\\dev_tools\\Python\\Python39\\python.exe"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 for /f "delims=" %%i in ('where python') do if not defined PYEXE set "PYEXE=%%i"
)
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%i in ('where py') do if not defined PYEXE set "PYEXE=%%i"
    set "PYARGS=-3"
  )
)
if not defined PYEXE (
  echo.
  echo 没有找到 Python，无法启动。请先安装 Python 或联系助手。
  echo 没有找到 Python >> "%LOGFILE%"
  echo.
  pause
  popd
  exit /b 1
)
echo 使用解释器：%PYEXE% %PYARGS% >> "%LOGFILE%"
"""

FOOTER = """set "RC=%ERRORLEVEL%"
echo 退出码：%RC% >> "%LOGFILE%"
if not "%RC%"=="0" (
  echo.
  echo {fail_text}（代码 %RC%）。请把工具目录里的「启动日志.txt」发给助手。
  echo.
  pause
)
popd
endlocal
"""


def write(name: str, text: str, folder: pathlib.Path) -> None:
    lines = text.replace("\r\n", "\n").split("\n")
    data = "\r\n".join(lines).encode("utf-8")
    if not data.endswith(b"\r\n"):
        data += b"\r\n"
    target = folder / name
    target.write_bytes(data)
    print("written", target, target.stat().st_size)


def main() -> None:
    write(
        "启动工具.bat",
        HEADER.format(title="启动工具")
        + '\necho 正在启动「快手自动发布助手」，请稍等几秒...\n'
        + '"%PYEXE%" %PYARGS% -X utf8 -m app.main\n'
        + FOOTER.format(fail_text="启动失败"),
        TOOL,
    )
    # 无控制台版本（普通用户用这个，看不到黑窗口）
    hidden = HEADER.format(title="启动工具(隐藏窗口)") + (
        '\nset "PYW=%PYEXE:python.exe=pythonw.exe%"\n'
        "if not exist \"%PYW%\" set \"PYW=%PYEXE%\"\n"
        '"%PYW%" %PYARGS% -X utf8 -m app.main\n'
    ) + FOOTER.format(fail_text="启动失败")
    write("启动工具-隐藏窗口.bat", hidden, TOOL)
    write(
        "自检.bat",
        HEADER.format(title="环境自检")
        + '\necho 正在自检（不会打开浏览器、不会操作账号）...\n"%PYEXE%" %PYARGS% -X utf8 -m app.selftest\n'
        + FOOTER.format(fail_text="执行失败"),
        TOOL,
    )
    write(
        "准备浏览器配置.bat",
        HEADER.format(title="准备浏览器配置")
        + "\necho 准备自动化专用的浏览器配置（保留登录态，不影响日常使用）\n"
        + '"%PYEXE%" %PYARGS% -X utf8 -m app.prepare_profiles\n'
        + FOOTER.format(fail_text="执行失败"),
        TOOL,
    )
    write(
        "运行勘查.bat",
        HEADER.format(title="页面勘查")
        + "\necho 页面勘查：打开真实后台页面抓取结构（只浏览，不会发布）\n"
        + '"%PYEXE%" %PYARGS% -X utf8 -m app.recon %*\n'
        + FOOTER.format(fail_text="执行失败"),
        TOOL,
    )
    probe_dir = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\work")
    write(
        "probe2.bat",
        HEADER.format(title="探针")
        + '\necho TEMPLATE_OK 解释器=%PYEXE% 附加=%PYARGS%\n'
        + '"%PYEXE%" %PYARGS% -X utf8 -c "print(\'PYTHON_RUN_OK\')"\n'
        + FOOTER.format(fail_text="执行失败"),
        probe_dir,
    )


if __name__ == "__main__":
    main()
