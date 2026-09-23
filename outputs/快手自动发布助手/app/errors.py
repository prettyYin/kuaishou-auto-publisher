# -*- coding: utf-8 -*-
"""流程中使用的异常类型。"""
from __future__ import annotations


class FlowError(RuntimeError):
    """流程类错误基类。"""


class StoppedByUser(FlowError):
    """用户点了停止。"""


class PageChanged(FlowError):
    """页面结构变化 / 找不到关键元素，继续操作有风险。"""


class UncertainResult(FlowError):
    """结果不确定（例如发布可能已提交）。按规则必须停下人工确认，不自动重试。"""


class DefiniteFailure(FlowError):
    """明确失败（例如文件都没选上），可以安全重试一次。"""


class LoginRequired(FlowError):
    """需要重新登录（扫码）。"""


class SkipVideo(FlowError):
    """当前这一条视频未通过可选设置校验，跳过且不发布。"""
