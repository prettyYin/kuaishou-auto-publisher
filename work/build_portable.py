# -*- coding: utf-8 -*-
"""打包免安装绿色版：自带 Python 运行时 + 必需库 + 工具本体，压缩成一个 zip。"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

PYTHON = Path(r"F:\MySofeware\dev_tools\Python\Python39")
TOOL = Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")
BUILD = Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\work\portable")
BUNDLE = BUILD / "快手自动发布助手-免安装版"
ZIP_PATH = TOOL.parent / "快手自动发布助手-免安装版.zip"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
LAUNCHER_SOURCE = Path(__file__).with_name("launcher.cs")

NEEDED_PACKAGES = ["playwright", "openpyxl", "et_xmlfile", "pyee", "greenlet", "typing_extensions"]
SKIP_LIB_DIRS = {"test", "tests", "idlelib", "lib2to3", "turtledemo", "ensurepip", "venv", "__pycache__"}


def copy_python_core() -> None:
    target = BUNDLE / "python"
    target.mkdir(parents=True, exist_ok=True)
    for item in PYTHON.iterdir():
        if item.is_file():
            shutil.copy2(item, target / item.name)
    for folder in ("DLLs", "tcl"):
        source = PYTHON / folder
        if source.is_dir():
            shutil.copytree(source, target / folder, dirs_exist_ok=True)
    for item in (PYTHON / "Lib").iterdir():
        if item.name in ("site-packages", "__pycache__") or item.name in SKIP_LIB_DIRS:
            continue
        if item.is_dir():
            shutil.copytree(
                item,
                target / "Lib" / item.name,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "test", "tests"),
            )
        else:
            (target / "Lib").mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target / "Lib" / item.name)
    print("Python runtime copied")


def copy_packages() -> None:
    target = BUNDLE / "python" / "Lib" / "site-packages"
    target.mkdir(parents=True, exist_ok=True)
    src = PYTHON / "Lib" / "site-packages"
    for name in NEEDED_PACKAGES:
        source = src / name
        if source.is_dir():
            shutil.copytree(source, target / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    for pattern in ("playwright-*.dist-info", "openpyxl-*.dist-info", "pyee-*.dist-info", "greenlet-*.dist-info"):
        for item in src.glob(pattern):
            shutil.copytree(item, target / item.name, dirs_exist_ok=True)
    print("packages copied")


def copy_tool() -> None:
    for name in ("app", "config"):
        shutil.copytree(TOOL / name, BUNDLE / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    # 只放一份图文说明（单文件 HTML，图片已内嵌），避免图片文件夹增加使用门槛
    manual = TOOL / "使用说明.html"
    if manual.exists():
        shutil.copy2(manual, BUNDLE / manual.name)
    # 打包给别人用的配置里不能带我的账号信息：账号清空，只保留公共地址与节奏设置
    import json

    cfg = json.loads((TOOL / "config" / "config.json").read_text(encoding="utf-8"))
    cfg["accounts"] = []
    cfg.pop("automation_data_dir", None)
    jinniu = cfg.setdefault("jinniu", {})
    base_url = str(jinniu.get("video_library_url") or "https://niu.e.kuaishou.com/material/supervideo")
    jinniu["video_library_url"] = base_url.split("?")[0].split("&")[0] or "https://niu.e.kuaishou.com/material/supervideo"
    jinniu.pop("rename_mode", None)
    creator = cfg.setdefault("creator", {})
    creator["post_publish_wait_seconds"] = 15
    (BUNDLE / "config" / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for folder in ("logs", "runs", "报表"):
        (BUNDLE / folder).mkdir(parents=True, exist_ok=True)
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        'start "" "%~dp0启动工具.exe"',
        "exit /b 0",
        "",
    ]
    (BUNDLE / "启动工具.bat").write_bytes("\r\n".join(lines).replace("\r\n\r\n", "\r\n").encode("utf-8"))
    log_lines = [
        "@echo off",
        "chcp 65001 >nul",
        'pushd "%~dp0"',
        "echo 带日志窗口启动（排查问题时用，正常情况下不需要用它）...",
        '"%~dp0python\\python.exe" -X utf8 -m app.main',
        "echo.",
        "echo 程序已退出。若有报错，请把上面的内容发给管理员。",
        "pause",
        "popd",
        "",
    ]
    (BUNDLE / "启动工具-显示日志.bat").write_bytes(
        "\r\n".join(log_lines).replace("\r\n\r\n", "\r\n").encode("utf-8")
    )
    print("tool copied")


def build_launcher(target_dir: Path) -> None:
    """用系统自带 C# 编译器生成无控制台窗口的启动器。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    exe = target_dir / "启动工具.exe"
    if not CSC.exists():
        print("launcher skipped: csc not found: %s" % CSC)
        return
    subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/target:winexe",
            "/out:%s" % exe,
            str(LAUNCHER_SOURCE),
        ],
        check=True,
    )
    vbs = (
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        'Set shell = CreateObject("WScript.Shell")\r\n'
        "folder = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        'exe = folder & "\\启动工具.exe"\r\n'
        "If fso.FileExists(exe) Then\r\n"
        '  shell.Run """" & exe & """", 0, False\r\n'
        "Else\r\n"
        '  py = folder & "\\python\\pythonw.exe"\r\n'
        "  If fso.FileExists(py) Then\r\n"
        '    shell.Run """" & py & """ -X utf8 -m app.main", 0, False\r\n'
        "  Else\r\n"
        '    MsgBox "缺少启动文件，请重新解压整个压缩包。", vbExclamation, "快手自动发布助手"\r\n'
        "  End If\r\n"
        "End If\r\n"
    )
    (target_dir / "启动工具（无窗口）.vbs").write_bytes(vbs.encode("utf-16"))
    print("launcher: %s" % exe)


def make_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in BUNDLE.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(BUNDLE.parent))
    print("zip: %s (%.1f MB)" % (ZIP_PATH, ZIP_PATH.stat().st_size / 1048576))


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    BUNDLE.mkdir(parents=True, exist_ok=True)
    copy_python_core()
    copy_packages()
    copy_tool()
    build_launcher(BUNDLE)
    make_zip()


if __name__ == "__main__":
    main()
