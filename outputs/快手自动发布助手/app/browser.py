# -*- coding: utf-8 -*-
"""Chrome 接管：配置副本、启动调试端口、连接 Playwright、阻止休眠。"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .errors import StoppedByUser

SKIP_DIR_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "GraphiteDawnCache",
    "GrShaderCache",
    "ShaderCache",
    "Media Cache",
    "Crashpad",
    "BrowserMetrics",
    "component_crx_cache",
    "extensions_crx_cache",
    "OptimizationHints",
    "PersistentOriginTrials",
    "Safe Browsing",
    "segmentation_platform",
    "TpcdMetadata",
    "AutofillStates",
    "MEIPreload",
    "WidevineCdm",
    "ZxcvbnData",
    "hyphen-data",
    "file-system",
    "GCM Store",
    "ClientCertificates",
    "Sessions",
}

SKIP_FILE_NAMES = {
    "Current Session",
    "Current Tabs",
    "Last Session",
    "Last Tabs",
}

SKIP_FILE_SUFFIX = (".log", ".pma", "-journal", "-wal", "-shm")

# 只复制与登录态相关的小文件，几秒钟就能完成（整份配置可能有几个 GB）
LEAN_KEEP = (
    "Network/Cookies",
    "Network/Cookies-journal",
    "Network/Network Persistent State",
    "Network/TransportSecurity",
    "Local Storage",
    "Session Storage",
    "IndexedDB",
    "Preferences",
    "Secure Preferences",
    "Web Data",
    "Login Data",
    "Login Data For Account",
    "Affiliation Database",
    "Reporting and NEL",
)


def _keep_lean(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == item or rel.startswith(item + "/") for item in LEAN_KEEP)


def list_chrome_profiles(user_data_dir: str | Path) -> List[Tuple[str, str]]:
    """读取 Chrome 的 Local State，返回 [(配置目录名, 显示名)]。"""
    user_data_dir = Path(str(user_data_dir))
    state_file = user_data_dir / "Local State"
    result: List[Tuple[str, str]] = []
    if not state_file.exists():
        return result
    try:
        raw = state_file.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(raw)
        info = (data.get("profile") or {}).get("info_cache") or {}
        for dir_name, meta in info.items():
            result.append((dir_name, (meta or {}).get("name") or dir_name))
    except Exception:
        return result
    result.sort(key=lambda pair: pair[0])
    return result


def _ignore(directory: str, names: List[str]) -> set:
    ignored = set()
    for name in names:
        if name in SKIP_DIR_NAMES or name in SKIP_FILE_NAMES or name.endswith(SKIP_FILE_SUFFIX):
            ignored.add(name)
    return ignored


def copy_profile(
    src_user_data: str | Path,
    src_profile: str,
    dst_user_data: str | Path,
    fresh: bool = False,
    logger=None,
    should_stop=None,
    mode: str = "lean",
    progress=None,
) -> Path:
    """把一个 Chrome 用户配置复制成独立的自动化副本（保留登录态）。

    目标结构：<dst_user_data>/Local State + <dst_user_data>/Default/*
    mode="lean" 时只复制登录相关的小文件（几秒钟完成）；"full" 为整份复制。
    """
    src_user_data = Path(str(src_user_data))
    dst_user_data = Path(str(dst_user_data))
    src_profile_dir = src_user_data / src_profile
    if not src_profile_dir.is_dir():
        raise FileNotFoundError("找不到 Chrome 配置目录：%s" % src_profile_dir)
    if fresh and dst_user_data.exists():
        shutil.rmtree(dst_user_data, ignore_errors=True)
    dst_default = dst_user_data / "Default"
    dst_user_data.mkdir(parents=True, exist_ok=True)
    dst_default.mkdir(parents=True, exist_ok=True)
    local_state = src_user_data / "Local State"
    if local_state.exists():
        try:
            shutil.copy2(local_state, dst_user_data / "Local State")
        except Exception as exc:
            if logger:
                logger.warning("复制 Local State 失败：%s", exc)
    errors: List[str] = []
    copied = 0
    if mode == "full":
        try:
            shutil.copytree(src_profile_dir, dst_default, ignore=_ignore, dirs_exist_ok=True)
        except shutil.Error as exc:
            for item in (exc.args[0] if exc.args else []):
                errors.append(str(item))
    else:
        for root, dirs, files in os.walk(src_profile_dir):
            rel_root = Path(root).relative_to(src_profile_dir)
            rel_root_text = str(rel_root).replace("\\", "/")
            if rel_root_text == ".":
                rel_root_text = ""
            for name in list(files):
                rel = ("%s/%s" % (rel_root_text, name)) if rel_root_text else name
                if not _keep_lean(rel):
                    continue
                if should_stop is not None and should_stop():
                    raise StoppedByUser("已按你的要求停止（正在复制浏览器配置）")
                source = Path(root) / name
                target = dst_default / rel.replace("/", os.sep)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied += 1
                    if progress and copied % 200 == 0:
                        progress("正在复制浏览器配置…已复制 %d 个文件" % copied)
                except Exception as exc:
                    errors.append("%s: %s" % (rel, exc))
    if logger:
        logger.info(
            "浏览器配置复制完成：%s（模式=%s，文件数=%d，失败=%d）",
            dst_user_data, mode, copied if mode != "full" else -1, len(errors),
        )
    return dst_user_data


def pick_free_port(preferred: int, logger=None) -> int:
    """首选端口被占用时自动往后找一个空闲端口。"""
    for offset in range(0, 40):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到空闲端口（从 %d 开始尝试）" % preferred)


def cdp_endpoint(port: int, timeout: float = 3.0) -> Optional[str]:
    """查询调试端口，返回 webSocketDebuggerUrl。"""
    url = "http://127.0.0.1:%d/json/version" % port
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return data.get("webSocketDebuggerUrl")
    except Exception:
        return None


def processes_using(user_data_dir: str | Path) -> List[int]:
    """找出正在使用某个数据目录的浏览器进程（只用于关闭自动化窗口）。"""
    if os.name != "nt":
        return []
    fragment = str(user_data_dir).replace("'", "''")
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*%s*' } | "
        "Select-Object -ExpandProperty ProcessId" % fragment
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
        return [int(line) for line in (result.stdout or "").split() if line.strip().isdigit()]
    except Exception:
        return []


def close_processes(pids: List[int], logger=None) -> int:
    closed = 0
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            closed += 1
        except Exception:
            continue
    if logger and closed:
        logger.info("已关闭 %d 个残留的自动化浏览器进程", closed)
    return closed


class ChromeSession:
    """以调试端口启动真实 Chrome（非无头），供 Playwright 接管。"""

    def __init__(self, chrome_exe: str, port: int, user_data_dir: str | Path, logger=None) -> None:
        self.chrome_exe = chrome_exe
        self.port = int(port)
        self.user_data_dir = Path(str(user_data_dir))
        self.logger = logger
        self.proc: Optional[subprocess.Popen] = None
        self.attached_existing = False

    def _log(self, level: str, message: str, *args) -> None:
        if self.logger:
            getattr(self.logger, level)(message, *args)

    def is_running(self) -> bool:
        """本工具的自动化窗口是否还开着（浏览器进程仍在使用同一个数据目录）。"""
        if cdp_endpoint(self.port) is not None:
            return True
        return bool(processes_using(self.user_data_dir))

    def start(
        self,
        urls: Optional[List[str]] = None,
        timeout: float = 60.0,
        should_stop=None,
        progress=None,
    ) -> str:
        note = progress or (lambda text: None)
        # 1) 之前启动过的自动化窗口可能还开着：能复用就复用
        for offset in range(0, 6):
            candidate = self.port + offset
            endpoint = cdp_endpoint(candidate)
            if endpoint:
                self.port = candidate
                self.attached_existing = True
                self._log("info", "自动化浏览器窗口已开着，直接复用（端口 %d）", candidate)
                return endpoint
        if not Path(self.chrome_exe).exists():
            raise FileNotFoundError("找不到 Chrome：%s" % self.chrome_exe)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.port = pick_free_port(self.port, self.logger)
        # 2) 先直接启动（不做进程扫描，避免每次都要等十几秒）
        note("正在启动浏览器…")
        endpoint = self._launch_and_wait(urls, timeout=min(15.0, timeout), should_stop=should_stop, note=note)
        if endpoint:
            return endpoint
        # 3) 15 秒还没起来，多半是这个数据目录被残留窗口占用：清理后重试一次
        note("启动较慢，检查是否有残留窗口…")
        leftovers = processes_using(self.user_data_dir)
        if leftovers:
            self._log("info", "发现 %d 个残留的自动化浏览器进程，先关闭它们再启动", len(leftovers))
            note("正在清理残留的自动化窗口…")
            close_processes(leftovers, self.logger)
            time.sleep(2)
            note("重新启动浏览器…")
            endpoint = self._launch_and_wait(
                urls, timeout=max(timeout - 15.0, 20.0), should_stop=should_stop, note=note
            )
            if endpoint:
                return endpoint
        raise TimeoutError(
            "浏览器没有在约 %d 秒内启动完成。可能是数据目录被其他程序占用，或安全软件拦截了调试端口。"
            "数据目录：%s\n可以先到设置页点「关闭浏览器窗口」或「清理残留窗口」，再重试。"
            % (int(timeout), self.user_data_dir)
        )

    def _launch_and_wait(self, urls, timeout: float, should_stop, note) -> Optional[str]:
        args = [
            self.chrome_exe,
            "--remote-debugging-port=%d" % self.port,
            "--user-data-dir=%s" % str(self.user_data_dir),
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-infobars",
            "--start-maximized",
        ]
        args.extend(urls or [])
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        self._log("info", "启动 Chrome：端口 %s，数据目录 %s", self.port, self.user_data_dir)
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        deadline = time.time() + timeout
        last_note = time.time()
        while time.time() < deadline:
            if should_stop is not None and should_stop():
                self.stop()
                raise StoppedByUser("已按你的要求停止（正在等待浏览器启动）")
            endpoint = cdp_endpoint(self.port)
            if endpoint:
                return endpoint
            if time.time() - last_note >= 3:
                elapsed = int(timeout - (deadline - time.time()))
                note("正在等待浏览器就绪…已等待 %d 秒" % elapsed)
                self._log("info", "等待自动化浏览器启动…已等待 %d 秒", elapsed)
                last_note = time.time()
            time.sleep(1.0)
        self.stop()
        return None

    def stop(self) -> None:
        if self.proc is None or self.attached_existing:
            return
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self._log("info", "已关闭该账号的自动化 Chrome 窗口")
        except Exception as exc:
            self._log("warning", "关闭 Chrome 失败：%s", exc)
        finally:
            self.proc = None


class SleepGuard:
    """运行期间阻止系统自动休眠（允许屏幕关闭）。"""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __enter__(self) -> "SleepGuard":
        if os.name == "nt":
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
                )
            except Exception:
                pass
        return self

    def __exit__(self, *exc_info) -> None:
        if os.name == "nt":
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            except Exception:
                pass


def set_files_via_cdp(context, page, files, selector: str = "input[type=file]") -> bool:
    """用 CDP 直接把本地文件路径交给浏览器。

    Playwright 自带的 set_input_files 在通过调试端口连接时限制 50MB，
    而 CDP 的 DOM.setFileInputFiles 是让浏览器自己读本地文件，没有这个限制。
    """
    paths = [str(Path(str(item))) for item in files]
    session = None
    try:
        session = context.new_cdp_session(page)
        session.send("DOM.enable")
        document = session.send("DOM.getDocument", {"depth": -1})
        node = session.send(
            "DOM.querySelector",
            {"nodeId": document["root"]["nodeId"], "selector": selector},
        )
        node_id = (node or {}).get("nodeId")
        if not node_id:
            return False
        session.send("DOM.setFileInputFiles", {"files": paths, "nodeId": node_id})
        return True
    except Exception:
        return False
    finally:
        try:
            if session is not None:
                session.detach()
        except Exception:
            pass


def attached_page(playwright, endpoint: str, url_hint: str = ""):
    """连接现有 Chrome，返回 (browser, context, page)。"""
    browser = playwright.chromium.connect_over_cdp(endpoint)
    contexts = browser.contexts
    context = contexts[0] if contexts else browser.new_context()
    # 注意：playwright 的 page.url 是属性（字符串），不是方法
    pages = [pg for pg in context.pages if (pg.url or "") != "about:blank"]
    if url_hint:
        host = url_hint.split("//")[-1].split("/")[0]
        for page in pages:
            if host and host in (page.url or ""):
                return browser, context, page
    page = pages[0] if pages else (context.pages[0] if context.pages else context.new_page())
    return browser, context, page
