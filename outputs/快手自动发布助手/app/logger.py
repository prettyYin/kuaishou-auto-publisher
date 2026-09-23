# -*- coding: utf-8 -*-
"""日志：文件 + 控制台 + 界面回调。"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class _UiHandler(logging.Handler):
    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.sink(self.format(record))
        except Exception:  # 界面已关闭时静默忽略
            pass


def setup_logger(
    log_dir: Path,
    level: str = "INFO",
    ui_sink: Optional[Callable[[str], None]] = None,
    tag: str = "",
) -> logging.Logger:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    name = "run_%s%s.log" % (stamp, ("_" + tag) if tag else "")
    logger = logging.getLogger("kzauto")
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    file_handler = logging.FileHandler(log_dir / name, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # 用 pythonw（无控制台）启动时 sys.stdout 可能不可用，这里要跳过，否则写日志会报错
    if sys.stdout is not None:
        try:
            stream = logging.StreamHandler(sys.stdout)
            stream.setFormatter(fmt)
            logger.addHandler(stream)
        except Exception:
            pass

    if ui_sink is not None:
        ui_handler = _UiHandler(ui_sink)
        ui_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger.addHandler(ui_handler)

    logger.propagate = False
    logger.info("日志文件：%s", log_dir / name)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("kzauto")
