# -*- coding: utf-8 -*-
"""阶段一：快手创作者服务平台——逐条上传、填广告语标题、发布。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .errors import (
    DefiniteFailure,
    LoginRequired,
    PageChanged,
    SkipVideo,
    StoppedByUser,
    UncertainResult,
)
from .browser import set_files_via_cdp
from .publish_settings import (
    AUTHOR_NONE_LABEL,
    month_number,
    normalize_publish_at,
    parse_publish_at,
    run_with_retries,
    schedule_time_values,
    validate_publish_at,
    year_number,
)
from .selectors import (
    PageStructureError,
    Selectors,
    click_any,
    exists_any,
    fill_any,
    find_any,
    find_list,
    set_files_any,
)

FALLBACK: Dict[str, List[Dict[str, Any]]] = {
    "file_input": [{"css": "input[type=file]"}],
    "upload_trigger": [
        {"text": "上传视频"},
        {"text": "上传作品"},
        {"text": "点击上传"},
        {"text": "上传"},
    ],
    "title_input": [
        {"css": "#work-description-edit"},
        {"css": "[placeholder*='作品描述']"},
        {"css": "[contenteditable=true]"},
        {"placeholder": "添加作品描述"},
        {"placeholder": "作品描述"},
        {"placeholder": "添加描述"},
        {"placeholder": "标题"},
        {"css": "textarea"},
    ],
    "publish_button": [
        {"css": "[class*='_edit-section-btns_'] div[class*='_button-primary_']"},
        {"css": "div[class*='_button-primary_']"},
        {"role": "button", "name": "发布", "exact": True},
        {"css": "button.ant-btn-primary"},
        {"role": "button", "name": "发布"},
        {"text": "发布"},
        {"text": "立即发布"},
    ],
    "publish_confirm_button": [
        {"text": "确认发布"},
        {"text": "确定"},
        {"text": "确认"},
    ],
    "success_toast": [
        {"css": ".ant-message-success"},
        {"css": "[class*='message-success']"},
        {"text": "发布成功"},
        {"text": "定时发布成功"},
        {"text": "预约发布成功"},
        {"text": "提交成功"},
        {"text": "已发布成功"},
    ],
    "failure_toast": [
        {"css": ".ant-message-error"},
        {"css": "[class*='message-error']"},
        {"text": "上传失败"},
        {"text": "发布失败"},
        {"text": "审核不通过"},
    ],
    "uploading_indicator": [
        {"text": "上传中"},
        {"text": "正在上传"},
        {"text": "上传进度"},
        {"text": "转码中"},
        {"text": "视频处理中"},
        {"text": "处理中"},
    ],
    "continue_button": [
        {"text": "继续发布"},
        {"text": "再发一条"},
        {"text": "发布新作品"},
    ],
    "login_hint": [
        {"text": "扫码登录"},
        {"text": "登录后"},
    ],
    "download_checkbox": [
        {"css": "label:has-text('允许下载此作品') input[type=checkbox]"},
        {"css": "label:has-text('允许下载') input[type=checkbox]"},
    ],
    "author_statement_select": [
        {"css": "div:has(> label:has-text('作者声明')) div.ant-select-selector"},
        {"css": "div:has(label:has-text('作者声明')) div.ant-select-selector"},
        {"css": "div[class*='edit-form-item']:has(label:has-text('作者声明')) .ant-select-selector"},
    ],
    "author_statement_selected": [
        {"css": "div:has(> label:has-text('作者声明')) .ant-select-selection-item"},
        {"css": "div[class*='edit-form-item']:has(label:has-text('作者声明')) .ant-select-selection-item"},
    ],
    "author_statement_placeholder": [
        {"css": "div:has(> label:has-text('作者声明')) .ant-select-selection-placeholder"},
        {"css": "div[class*='edit-form-item']:has(label:has-text('作者声明')) .ant-select-selection-placeholder"},
    ],
    "author_statement_clear": [
        {"css": "div:has(> label:has-text('作者声明')) .ant-select-clear"},
        {"css": "div[class*='edit-form-item']:has(label:has-text('作者声明')) .ant-select-clear"},
    ],
    "author_statement_option": [
        {"css": ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option"},
        {"css": ".ant-select-dropdown .ant-select-item-option"},
    ],
    "immediate_radio": [
        {"css": "div:has(> div:has-text('发布时间')) label:has-text('立即发布') input[type=radio]"},
        {"css": "div[class*='publish-time'] label:has-text('立即发布') input[type=radio]"},
        {"css": "label:has-text('立即发布') input[type=radio]"},
        {"text": "立即发布"},
    ],
    "schedule_radio": [
        {"css": "div:has(> div:has-text('发布时间')) label:has-text('定时发布') input[type=radio]"},
        {"css": "div[class*='publish-time'] label:has-text('定时发布') input[type=radio]"},
        {"css": "label:has-text('定时发布') input[type=radio]"},
        {"text": "定时发布"},
    ],
    "schedule_input": [
        {"css": "input[placeholder='选择日期时间']"},
        {"css": ".ant-picker-input input[placeholder*='请选择']"},
        {"css": "div[class*='publish-time'] .ant-picker-input input"},
        {"css": "div.ant-picker input"},
        {"css": ".ant-picker-input input"},
        {"css": "input[placeholder*='日期']"},
        {"css": "input[placeholder*='时间']"},
        {"css": "input[placeholder*='发布时间']"},
    ],
    "schedule_selected": [
        {"css": "input[placeholder='选择日期时间']"},
        {"css": "div[class*='publish-time'] .ant-picker-input input"},
        {"css": "div.ant-picker input"},
        {"css": ".ant-picker-input input"},
        {"css": "input[placeholder*='日期']"},
        {"css": "input[placeholder*='时间']"},
        {"css": "input[placeholder*='发布时间']"},
    ],
    "schedule_dropdown": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"},
    ],
    "schedule_prev_month": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) button.ant-picker-header-prev-btn"},
    ],
    "schedule_next_month": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) button.ant-picker-header-next-btn"},
    ],
    "schedule_year_label": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-year-btn"},
    ],
    "schedule_month_label": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-month-btn"},
    ],
    "schedule_time_columns": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-time-panel-column"},
    ],
    "schedule_ok_button": [
        {"css": ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-ok button"},
        {"text": "确定", "exact": True},
    ],
    "page_error": [
        {"text": "应用加载失败"},
        {"text": "请刷新重试"},
        {"text": "页面加载失败"},
        {"text": "网络异常"},
    ],
    "resume_dialog": [
        {"css": "button[class*='_renounce-btn_']"},
        {"text": "放弃"},
    ],
}


class CreatorContext:
    """一次账号运行所需的上下文。"""

    def __init__(
        self,
        bridge,
        page,
        cfg,
        account,
        videos,
        copies,
        state,
        logger,
        video_settings: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
    ):
        self.bridge = bridge
        self.page = page
        self.cfg = cfg
        self.account = account
        self.videos = videos
        self.copies = copies
        self.video_settings = list(video_settings or [])
        self.state = state
        self.logger = logger
        self.dry_run = dry_run
        self.selectors = Selectors.load()
        self.creator = cfg.get("creator", {})


def _cands(ctx: CreatorContext, key: str) -> List[Dict[str, Any]]:
    return ctx.selectors.merged("creator", key, FALLBACK[key])


def _check_login(ctx: CreatorContext) -> None:
    url = (ctx.page.url or "").lower()
    if "login" in url or "passport" in url:
        raise LoginRequired("当前是登录页（%s），请先扫码登录。" % ctx.page.url)
    if exists_any(ctx.page, _cands(ctx, "login_hint")):
        raise LoginRequired("页面上出现登录提示，请先在该 Chrome 窗口完成扫码登录。")


def same_site(current_url: str, target_url: str) -> bool:
    """当前页面是否已经在目标站点上（防止在错误页面误操作）。"""
    host = (target_url or "").split("//")[-1].split("/")[0]
    if not host:
        return True
    return host in (current_url or "")


def recover_page_errors(ctx: CreatorContext, attempts: int = 2) -> bool:
    """创作者平台出现「应用加载失败」时，先自动刷新 2 次再决定是否放弃。"""
    for attempt in range(max(int(attempts), 1)):
        if not exists_any(ctx.page, _cands(ctx, "page_error")):
            return True
        shot = ctx.bridge.shot(ctx.page, "应用加载失败_第%d次刷新" % (attempt + 1))
        ctx.logger.warning(
            "页面显示「应用加载失败」，正在自动刷新重试（第 %d/%d 次）；截图 %s",
            attempt + 1,
            attempts,
            shot or "无",
        )
        try:
            ctx.page.reload(wait_until="domcontentloaded", timeout=60000)
            ctx.page.wait_for_timeout(2500)
        except Exception as exc:
            ctx.logger.warning("自动刷新失败：%s", exc)
    if exists_any(ctx.page, _cands(ctx, "page_error")):
        raise DefiniteFailure("创作者平台连续刷新 %d 次后仍然显示「应用加载失败」" % attempts)
    return True


def page_has_load_error(ctx: CreatorContext) -> bool:
    return exists_any(ctx.page, _cands(ctx, "page_error"))


def goto_creator_page(ctx: CreatorContext, url: str, attempts: int = 2) -> None:
    """打开发布页时如果页面已崩溃，先恢复再跳转，避免卡在超长 goto 上。"""
    for attempt in range(max(int(attempts), 1)):
        if page_has_load_error(ctx):
            recover_page_errors(ctx, attempts=2)
        try:
            ctx.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            ctx.page.wait_for_timeout(1800)
        except Exception as exc:
            ctx.logger.warning(
                "打开发布页失败或超时（第 %d/%d 次）：%s",
                attempt + 1,
                attempts,
                exc,
            )
        recover_page_errors(ctx, attempts=2)
        if not page_has_load_error(ctx) and same_site(ctx.page.url or "", url):
            return
    raise DefiniteFailure("连续 %d 次都打不开创作者发布页" % attempts)


def ensure_upload_page(ctx: CreatorContext, force_navigate: bool = False):
    """确保当前页面可以上传视频，返回文件输入框 Locator。"""
    publish_url = ctx.creator.get("publish_url") or ""
    current_url = ctx.page.url or ""
    # 必须站在创作者平台的页面上，否则可能把文件塞进别的页面（比如金牛的上传入口）
    if publish_url and not same_site(current_url, publish_url) and not force_navigate:
        ctx.logger.info("当前页面 %s 不是发布页，先跳转到 %s", current_url or "空白页", publish_url)
        goto_creator_page(ctx, publish_url, attempts=2)
        handle_resume_dialog(ctx)
    if force_navigate and publish_url:
        ctx.logger.info("重新打开上传页：%s", publish_url)
        goto_creator_page(ctx, publish_url, attempts=2)
        ctx.page.wait_for_timeout(500)
    recover_page_errors(ctx, attempts=2)
    _check_login(ctx)
    handle_resume_dialog(ctx)
    file_input = find_any(ctx.page, _cands(ctx, "file_input"), timeout=8, need_visible=False)
    if file_input is not None:
        return file_input
    if ctx.creator.get("manual_rescue", True):
        answer = ctx.bridge.rescue(
            "需要你手动打开上传页",
            "当前页面没找到上传入口（浏览器可能刚崩溃过）。\n"
            "你可以选「帮我重新打开上传页」让脚本自己刷新一下；\n"
            "也可以在这个浏览器窗口里自己打开「创作者服务平台 → 发布作品 / 上传视频」，再选第一项。",
            ["帮我重新打开上传页", "我已经打开好了，继续", "跳过这个账号", "停止运行"],
        )
        if answer == "跳过这个账号":
            raise StoppedByUser("用户选择跳过该账号")
        if answer == "停止运行":
            raise StoppedByUser("用户停止运行")
        if answer == "帮我重新打开上传页":
            publish_url = ctx.creator.get("publish_url") or ""
            if publish_url:
                ctx.logger.info("重新打开上传页：%s", publish_url)
                try:
                    goto_creator_page(ctx, publish_url, attempts=2)
                    ctx.page.wait_for_timeout(700)
                    handle_resume_dialog(ctx)
                except Exception as exc:
                    ctx.logger.warning("重新打开上传页失败：%s", exc)
        file_input = find_any(ctx.page, _cands(ctx, "file_input"), timeout=20, need_visible=False)
        if file_input is not None:
            return file_input
    raise PageChanged("页面上找不到 input[type=file]，无法上传视频")


def handle_resume_dialog(ctx: CreatorContext) -> None:
    """上传页会问「还有上次未发布的视频，是否继续编辑？」——默认放弃草稿，继续新流程。"""
    dialog = find_any(ctx.page, _cands(ctx, "resume_dialog"), timeout=2)
    if dialog is None:
        return
    mode = str(ctx.creator.get("on_resume_dialog", "dismiss")).lower()
    if mode == "ask" and ctx.creator.get("manual_rescue", True):
        answer = ctx.bridge.rescue(
            "上传页有上次未发布的草稿",
            "创作者平台提示「还有上次未发布的视频，是否继续编辑？」\n\n"
            "选「放弃草稿，继续新上传」会丢弃那个未发布的草稿（通常是我们上次中断留下的）；\n"
            "也可以自己先在浏览器里处理，再选继续。",
            ["放弃草稿，继续新上传", "我已经手动处理好了，继续", "停止运行"],
        )
        if answer == "停止运行":
            raise StoppedByUser("用户停止运行")
        if answer == "我已经手动处理好了，继续":
            return
    try:
        dialog.click()
        ctx.logger.info("已处理「上次未发布草稿」的提示（放弃草稿）")
        ctx.page.wait_for_timeout(1200)
    except Exception as exc:
        ctx.logger.warning("处理草稿提示失败：%s", exc)


def wait_upload_ready(ctx: CreatorContext, file_name: str) -> None:
    """等待上传/转码完成（标题框可用、发布按钮可点）。"""
    timeout = int(ctx.creator.get("upload_timeout_seconds", 1800))
    stall_limit = float(ctx.creator.get("no_progress_seconds", 180))  # 卡住多久就放弃等待
    started = time.time()
    deadline = started + timeout
    last_progress = started
    last_seen_state = ""
    last_note = 0.0
    title_ready_since: Optional[float] = None
    saw_uploading = False
    fallback_settle = float(ctx.creator.get("upload_settle_seconds", 10))
    while time.time() < deadline:
        if ctx.bridge.stopped():
            raise StoppedByUser("用户停止运行")
        # 页面本身崩了（例如"应用加载失败，请刷新重试"）→ 立刻刷新重试，不要干等
        if exists_any(ctx.page, _cands(ctx, "page_error")):
            recover_page_errors(ctx, attempts=2)
            last_progress = time.time()
            continue
        if time.time() - last_progress > stall_limit:
            shot = ctx.bridge.shot(ctx.page, "上传页无响应")
            raise DefiniteFailure(
                "等待 %s 上传超过 %.0f 秒没有任何进展（页面可能卡住），已截图 %s，将刷新后重试"
                % (file_name, stall_limit, shot or "无")
            )
        if exists_any(ctx.page, _cands(ctx, "failure_toast")):
            raise DefiniteFailure("页面出现上传/发布失败提示")
        uploading = exists_any(ctx.page, _cands(ctx, "uploading_indicator"))
        if uploading:
            saw_uploading = True
        title = find_any(ctx.page, _cands(ctx, "title_input"), timeout=0.4)
        publish = find_any(ctx.page, _cands(ctx, "publish_button"), timeout=0.4)
        ready = (
            title is not None
            and publish is not None
            and publish.is_enabled()
            and not uploading
        )
        state_key = "%s|%s|%s" % (title is not None, publish is not None, uploading)
        if state_key != last_seen_state:
            last_seen_state = state_key
            last_progress = time.time()
        if ready:
            if title_ready_since is None:
                title_ready_since = time.time()
            stable = time.time() - title_ready_since
            # 页面上真的出现过"上传中/转码中"，它消失了就说明传完了，可以马上发布
            need = 3.0 if saw_uploading else fallback_settle
            if stable >= need:
                ctx.logger.info(
                    "上传完成（%s，稳定 %.0f 秒），总用时 %.0f 秒",
                    "已看到上传提示并消失" if saw_uploading else "未检测到上传提示",
                    stable,
                    time.time() - started,
                )
                return
        else:
            title_ready_since = None
            if uploading and time.time() - last_note > 20:
                ctx.logger.info("视频正在上传/转码中…已等待 %d 秒", int(time.time() - started))
                last_note = time.time()
        if time.time() - last_note > 30:
            waited = int(time.time() - started)
            ctx.bridge.status("等待上传完成：%s（已等待 %d 秒）" % (file_name, waited))
            ctx.logger.info("等待 %s 上传/转码，已等待 %d 秒", file_name, waited)
            last_note = time.time()
        time.sleep(2)
    raise UncertainResult("等待上传/转码超过 %d 秒，请人工确认这一条是否已上传" % timeout)


def fill_title(ctx: CreatorContext, copy_text: str) -> None:
    fill_any(ctx.page, _cands(ctx, "title_input"), copy_text, timeout=30)
    ctx.logger.info("已填写标题：%s", copy_text)


def current_title(ctx: CreatorContext) -> str:
    """读取当前标题框里的文字（contenteditable 或 input 都支持）。"""
    locator = find_any(ctx.page, _cands(ctx, "title_input"), timeout=2)
    if locator is None:
        return ""
    for getter in ("inner_text", "input_value"):
        try:
            value = getattr(locator, getter)()
            if value:
                return str(value).strip()
        except Exception:
            continue
    return ""


def title_matches(ctx: CreatorContext, copy_text: str) -> bool:
    """标题是否已经是这句广告语（页面可能自动追加话题，所以用开头匹配）。"""
    text = current_title(ctx)
    head = "".join(copy_text.strip()[:10].split())
    if not text or not head:
        return False
    return head in "".join(text.split())


def title_is_complete(text: str, copy_text: str) -> bool:
    """标题必须完整包含整句广告语，不能在中间被截断。"""
    normalize = lambda value: "".join(str(value or "").split())
    target = normalize(copy_text)
    if not target:
        return False
    return target in normalize(text)


def ensure_title(ctx: CreatorContext, copy_text: str, attempts: int = 3) -> bool:
    """把标题写完整并校验；返回是否确认完整。"""
    for attempt in range(1, attempts + 1):
        current = current_title(ctx)
        if title_is_complete(current, copy_text):
            if attempt == 1:
                ctx.logger.info("标题校验通过（共 %d 字）", len("".join(copy_text.split())))
            return True
        fill_title(ctx, copy_text)
        ctx.page.wait_for_timeout(900)
        current = current_title(ctx)
        if title_is_complete(current, copy_text):
            ctx.logger.info("标题已补填完整（第 %d 次尝试，共 %d 字）", attempt, len("".join(copy_text.split())))
            return True
        ctx.logger.warning(
            "标题没写完整（第 %d 次尝试）：现在 %d 字 / 应为 %d 字",
            attempt,
            len("".join(str(current or "").split())),
            len("".join(copy_text.split())),
        )
    return False


def uncheck_download_permission(ctx: CreatorContext) -> None:
    """按你的要求：发布前把「允许下载此作品」取消勾选。"""
    if not ctx.creator.get("uncheck_download", True):
        return
    locator = find_any(ctx.page, _cands(ctx, "download_checkbox"), timeout=4)
    if locator is None:
        ctx.logger.info("没找到「允许下载此作品」，跳过这一步")
        return
    for attempt in range(2):
        try:
            if not locator.is_checked():
                ctx.logger.info("「允许下载此作品」当前未勾选")
                return
            try:
                locator.uncheck(timeout=6000)
            except Exception:
                locator.uncheck(timeout=6000, force=True)
            ctx.page.wait_for_timeout(400)
            if not locator.is_checked():
                ctx.logger.info("已取消勾选「允许下载此作品」")
                return
        except Exception as exc:
            ctx.logger.warning("取消「允许下载此作品」失败（第 %d 次）：%s", attempt + 1, exc)
        ctx.page.wait_for_timeout(600)
    try:
        if locator.is_checked():
            ctx.logger.error("「允许下载此作品」仍然是被勾选状态，请留意这一条")
    except Exception:
        pass


def _locator_text(locator) -> str:
    if locator is None:
        return ""
    for getter in ("inner_text", "input_value"):
        try:
            value = getattr(locator, getter)()
            if value:
                return str(value).strip()
        except Exception:
            continue
    for attr in ("title", "value", "aria-label"):
        try:
            value = locator.get_attribute(attr)
            if value:
                return str(value).strip()
        except Exception:
            continue
    return ""


def current_author_statement(ctx: CreatorContext) -> str:
    locator = find_any(ctx.page, _cands(ctx, "author_statement_selected"), timeout=1)
    if locator is not None:
        text = _locator_text(locator)
        if text:
            return text
    return ""


def clear_author_statement(ctx: CreatorContext) -> None:
    """把页面残留的作者声明清空；找不到字段时按“页面没有这一项”处理。"""
    select = find_any(ctx.page, _cands(ctx, "author_statement_select"), timeout=3)
    if select is None:
        ctx.logger.info("页面上没有找到「作者声明」，按不设置继续")
        return
    if not current_author_statement(ctx):
        return
    try:
        select.hover()
    except Exception:
        pass
    clear = find_any(
        ctx.page,
        _cands(ctx, "author_statement_clear"),
        timeout=2,
        need_visible=False,
    )
    if clear is None:
        raise PageStructureError("作者声明有残留选择，但页面上找不到清除按钮")
    try:
        clear.click(timeout=6000)
    except Exception:
        clear.click(force=True, timeout=6000)
    ctx.page.wait_for_timeout(450)
    remaining = current_author_statement(ctx)
    if remaining:
        raise PageStructureError("作者声明没有清空，页面仍显示：%s" % remaining)
    ctx.logger.info("已把作者声明恢复为「不设置」")


def select_author_statement(ctx: CreatorContext, target: str) -> None:
    select = find_any(ctx.page, _cands(ctx, "author_statement_select"), timeout=6)
    if select is None:
        raise PageStructureError("找不到「作者声明」下拉框")
    select.click(timeout=6000)
    ctx.page.wait_for_timeout(300)
    options = find_list(ctx.page, _cands(ctx, "author_statement_option"), min_count=1)
    if options is None:
        raise PageStructureError("作者声明下拉框没有展开或没有可选项")
    chosen = None
    for index in range(min(options.count(), 30)):
        item = options.nth(index)
        text = _locator_text(item)
        if text == target:
            chosen = item
            break
    if chosen is None:
        raise PageStructureError("作者声明下拉框里没有「%s」这个选项" % target)
    chosen.click(timeout=6000)
    ctx.page.wait_for_timeout(450)
    actual = current_author_statement(ctx)
    if actual != target:
        raise PageStructureError("作者声明回读不一致：页面显示「%s」，应为「%s」" % (actual or "空", target))
    ctx.logger.info("作者声明已选择：%s", target)


def apply_author_statement(ctx: CreatorContext, author_statement: str) -> None:
    target = str(author_statement or "").strip()
    if not target:
        target = ""
    retries = int(ctx.creator.get("author_statement_retries", 2))

    def action() -> None:
        try:
            if target:
                select_author_statement(ctx, target)
            elif ctx.creator.get("clear_author_statement_when_empty", True):
                clear_author_statement(ctx)
        except Exception:
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
            raise

    ok, error = run_with_retries(action, retries=retries)
    if not ok:
        raise SkipVideo("作者声明设置失败：%s" % (error or "未知原因"))


def read_schedule_value(ctx: CreatorContext) -> str:
    locator = find_any(ctx.page, _cands(ctx, "schedule_selected"), timeout=2)
    return _locator_text(locator)


def _radio_checked(locator) -> bool:
    try:
        return bool(locator.is_checked())
    except Exception:
        return False


def _ensure_radio(locator, label: str) -> None:
    if _radio_checked(locator):
        return
    try:
        locator.check(timeout=6000)
    except Exception:
        try:
            locator.click(force=True, timeout=6000)
        except Exception as exc:
            raise PageStructureError("找不到或点不动「%s」选项：%s" % (label, exc))
    if not _radio_checked(locator):
        raise PageStructureError("「%s」没有切换成功" % label)


def _picker_year_month(ctx: CreatorContext):
    year_label = find_any(ctx.page, _cands(ctx, "schedule_year_label"), timeout=1)
    month_label = find_any(ctx.page, _cands(ctx, "schedule_month_label"), timeout=1)
    return year_number(_locator_text(year_label)), month_number(_locator_text(month_label))


def _move_picker_to_month(ctx: CreatorContext, target_year: int, target_month: int) -> None:
    for _ in range(24):
        year, month = _picker_year_month(ctx)
        if not year or not month:
            return
        if (year, month) == (target_year, target_month):
            return
        if (target_year, target_month) > (year, month):
            click_any(ctx.page, _cands(ctx, "schedule_next_month"), timeout=5)
        else:
            click_any(ctx.page, _cands(ctx, "schedule_prev_month"), timeout=5)
        ctx.page.wait_for_timeout(350)
    raise PageStructureError("日期面板没有切换到 %04d-%02d" % (target_year, target_month))


def _pick_schedule_by_mouse(ctx: CreatorContext, target) -> None:
    """按平台要求，用鼠标在日期面板里选年月日时分，而不是直接往 input 里打字。"""
    field = find_any(ctx.page, _cands(ctx, "schedule_input"), timeout=5)
    if field is None:
        raise PageStructureError("找不到定时发布的日期输入框")
    dropdown = find_any(ctx.page, _cands(ctx, "schedule_dropdown"), timeout=1)
    if dropdown is None:
        field.click(timeout=6000)
        dropdown = find_any(ctx.page, _cands(ctx, "schedule_dropdown"), timeout=5)
    if dropdown is None:
        raise PageStructureError("日期时间面板没有打开")
    _move_picker_to_month(ctx, target.year, target.month)
    date_text = target.strftime("%Y-%m-%d")
    day_cell = ctx.page.locator(
        ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
        "td.ant-picker-cell[title='%s']" % date_text
    )
    if day_cell.count() == 0:
        raise PageStructureError("日期面板里找不到 %s" % date_text)
    day_cell.first.click(timeout=6000)
    ctx.page.wait_for_timeout(350)

    columns = find_list(ctx.page, _cands(ctx, "schedule_time_columns"), min_count=1)
    if columns is None:
        raise PageStructureError("日期面板里没有时分选择列")
    values = schedule_time_values(target, columns.count())
    if not values:
        raise PageStructureError("无法生成目标时间")
    for index, value in enumerate(values):
        if index >= columns.count():
            break
        cells = columns.nth(index).locator("li.ant-picker-time-panel-cell")
        chosen = None
        for cell_index in range(min(cells.count(), 61)):
            cell = cells.nth(cell_index)
            if _locator_text(cell) == value:
                chosen = cell
                break
        if chosen is None:
            raise PageStructureError("日期面板里找不到时间 %s" % value)
        chosen.click(timeout=6000)
    ctx.page.wait_for_timeout(250)
    ok_button = find_any(ctx.page, _cands(ctx, "schedule_ok_button"), timeout=4)
    if ok_button is None:
        raise PageStructureError("日期面板里找不到「确定」按钮")
    ok_button.click(timeout=6000)
    ctx.page.wait_for_timeout(600)


def apply_publish_schedule(ctx: CreatorContext, publish_at: str) -> None:
    target = normalize_publish_at(publish_at)
    if target:
        error = validate_publish_at(
            target,
            min_lead_minutes=int(ctx.creator.get("schedule_min_lead_minutes", 60)),
            max_days=int(ctx.creator.get("schedule_max_days", 14)),
        )
        if error:
            raise SkipVideo("定时时间不合规：%s" % error)
    retries = int(ctx.creator.get("author_statement_retries", 2))

    def action() -> None:
        try:
            if not target:
                immediate = find_any(ctx.page, _cands(ctx, "immediate_radio"), timeout=3)
                if immediate is not None:
                    _ensure_radio(immediate, "立即发布")
                    return
                scheduled = find_any(ctx.page, _cands(ctx, "schedule_radio"), timeout=2)
                if scheduled is not None and _radio_checked(scheduled):
                    raise PageStructureError("页面当前是定时发布，但找不到「立即发布」选项")
                ctx.logger.info("页面上没有「立即发布/定时发布」选项，按立即发布继续")
                return
            scheduled = find_any(ctx.page, _cands(ctx, "schedule_radio"), timeout=4)
            if scheduled is None:
                raise PageStructureError("找不到「定时发布」选项")
            _ensure_radio(scheduled, "定时发布")
            ctx.page.wait_for_timeout(350)
            parsed = parse_publish_at(target)
            if parsed is None:
                raise PageStructureError("定时时间格式不正确：%s" % target)
            try:
                _pick_schedule_by_mouse(ctx, parsed)
            except Exception as exc:
                raise PageStructureError(
                    "用鼠标在日期面板选择时间失败（不会直接往输入框打字）：%s" % exc
                )
            actual = read_schedule_value(ctx)
            if normalize_publish_at(actual) != target:
                raise PageStructureError(
                    "定时时间回读不一致：页面显示「%s」，应为「%s」" % (actual or "空", target)
                )
            ctx.logger.info("已设置定时发布：%s", parsed.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
            raise

    ok, error = run_with_retries(action, retries=retries)
    if not ok:
        raise SkipVideo("定时发布时间设置失败：%s" % (error or "未知原因"))
    if not target:
        ctx.logger.info("发布时间保持为立即发布")


def apply_publish_options(ctx: CreatorContext, setting: Optional[Dict[str, Any]]) -> None:
    data = dict(setting or {})
    apply_author_statement(ctx, str(data.get("author_statement") or ""))
    apply_publish_schedule(ctx, str(data.get("publish_at") or ""))


def run_extra_actions(ctx: CreatorContext) -> None:
    """执行账号级固定设置（话题、合集、地点等）。"""
    actions = list(ctx.account.get("extra_actions") or []) + list(ctx.creator.get("extra_actions") or [])
    for action in actions:
        kind = str(action.get("do") or "").lower()
        target = action.get("target") or []
        if isinstance(target, (str, dict)):
            target = [target]
        label = action.get("label") or kind
        if not target:
            continue
        try:
            if kind == "click":
                click_any(ctx.page, target, timeout=10)
            elif kind == "fill":
                fill_any(ctx.page, target, str(action.get("value", "")), timeout=10)
            elif kind == "check":
                locator = find_any(ctx.page, target, timeout=10)
                if locator is not None:
                    locator.check()
            elif kind == "set_files":
                set_files_any(ctx.page, target, [str(action.get("value", ""))])
            elif kind == "wait":
                ctx.page.wait_for_timeout(int(action.get("value", 1000)))
            else:
                ctx.logger.warning("跳过未知的附加动作：%s", kind)
                continue
            ctx.logger.info("已执行固定设置：%s", label)
        except Exception as exc:
            ctx.logger.warning("固定设置「%s」执行失败：%s", label, exc)


def click_publish(ctx: CreatorContext) -> None:
    try:
        click_any(ctx.page, _cands(ctx, "publish_button"), timeout=20)
    except PageStructureError:
        if not ctx.creator.get("manual_rescue", True):
            raise
        answer = ctx.bridge.rescue(
            "找不到发布按钮",
            "请在这个 Chrome 窗口里手动点击「发布」，或先确认页面是否正常。",
            ["我已经手动点过发布，继续", "重试自动查找", "停止运行"],
        )
        if answer == "停止运行":
            raise StoppedByUser("用户停止运行")
        if answer == "重试自动查找":
            click_any(ctx.page, _cands(ctx, "publish_button"), timeout=15)
    ctx.logger.info("已点击发布")
    confirm = find_any(ctx.page, _cands(ctx, "publish_confirm_button"), timeout=2.5)
    if confirm is not None:
        try:
            confirm.click()
            ctx.logger.info("已点击二次确认")
        except Exception:
            pass


def _grab_work_url(ctx: CreatorContext, copy_text: str) -> str:
    """尽量抓取刚发布作品的链接，抓不到不影响流程。"""
    try:
        links = ctx.page.locator("a[href*='photo'], a[href*='work'], a[href*='video']")
        count = min(links.count(), 8)
        head = copy_text[:8]
        for index in range(count):
            item = links.nth(index)
            href = item.get_attribute("href") or ""
            if not href:
                continue
            try:
                text = item.inner_text() or ""
            except Exception:
                text = ""
            if head and head in text:
                return href
    except Exception:
        pass
    return ""


def wait_publish_result(ctx: CreatorContext, copy_text: str) -> str:
    """等待发布结果，返回作品链接（可能为空）。"""
    timeout = int(ctx.creator.get("publish_confirm_timeout_seconds", 600))
    started = time.time()
    deadline = started + timeout
    last_note = 0.0
    asked = False
    while time.time() < deadline:
        if ctx.bridge.stopped():
            raise StoppedByUser("用户停止运行")
        current_url = ctx.page.url or ""
        low = current_url.lower()
        # 浏览器崩溃 / 页面空白时不能当成发布成功，必须停下（否则会把没发的记成已发）
        if (not low) or low.startswith("about:blank") or "chrome-error" in low or "about:neterror" in low:
            raise PageChanged("浏览器页面异常（%s），为避免误判为发布成功，已停止该账号" % (current_url or "空白页"))
        # 只有明确跳到「作品管理 / 内容管理」才算发布成功
        if "kuaishou.com" in low and ("/article/manage" in low or "manage/video" in low or "/content/manage" in low):
            ctx.logger.info("页面已跳转到作品管理页，判定发布成功：%s", current_url)
            return _grab_work_url(ctx, copy_text)
        if exists_any(ctx.page, _cands(ctx, "failure_toast")):
            raise UncertainResult("页面提示发布失败/审核不通过，请人工确认")
        if exists_any(ctx.page, _cands(ctx, "success_toast")):
            ctx.logger.info("检测到发布成功提示")
            return _grab_work_url(ctx, copy_text)
        works_url = ctx.creator.get("works_url") or ""
        if works_url and (ctx.page.url or "").startswith(works_url.rstrip("/")):
            ctx.logger.info("已跳转到作品管理页，视为发布成功")
            return _grab_work_url(ctx, copy_text)
        if time.time() - last_note > 20:
            ctx.logger.info("等待发布结果，已等待 %.0f 秒", time.time() - started)
            last_note = time.time()
        if not asked and time.time() - started > 45:
            asked = True
            shot = ctx.bridge.shot(ctx.page, "发布结果待确认")
            answer = ctx.bridge.rescue(
                "点了发布但页面没有反应",
                "已经点了「发布」，但 %d 秒内没看到发布成功的提示。\n"
                "截图已保存：%s\n\n"
                "你可以看一下那个浏览器窗口：如果已经提示发布成功，就选第一项继续；"
                "如果还停在发布页，就自己点一下「发布」再选第一项。" % (int(time.time() - started), shot or "无"),
                ["已经发布成功了，继续下一条", "我再手动点一次发布，然后继续", "停止运行"],
            )
            if answer == "停止运行":
                raise StoppedByUser("用户停止运行")
            if answer == "已经发布成功了，继续下一条":
                ctx.logger.info("用户确认已发布成功，继续")
                return _grab_work_url(ctx, copy_text)
            if answer == "我再手动点一次发布，然后继续":
                try:
                    click_any(ctx.page, _cands(ctx, "publish_button"), timeout=10)
                except Exception as exc:
                    ctx.logger.warning("再次点击发布失败：%s", exc)
        time.sleep(1.5)
    raise UncertainResult("等待发布结果超时，请人工确认这一条是否已发布成功")


def back_to_upload(ctx: CreatorContext) -> None:
    """回到上传页，准备下一条。"""
    continue_button = find_any(ctx.page, _cands(ctx, "continue_button"), timeout=2)
    if continue_button is not None:
        try:
            continue_button.click()
            ctx.page.wait_for_timeout(1500)
            return
        except Exception:
            pass
    publish_url = ctx.creator.get("publish_url") or ""
    if publish_url:
        goto_creator_page(ctx, publish_url, attempts=2)
        ctx.page.wait_for_timeout(500)


def publish_once(ctx: CreatorContext, video, copy_text: str, setting: Optional[Dict[str, Any]] = None):
    """上传一条视频；返回作品链接（演练模式返回 None）。"""
    data = dict(setting or {})
    file_input = ensure_upload_page(ctx)
    if not set_files_via_cdp(ctx.page.context, ctx.page, [video]):
        ctx.logger.warning("CDP 方式选择文件失败，改用普通方式（大文件可能被限制）")
        file_input.set_input_files(str(video))
    else:
        ctx.logger.info("已用 CDP 方式选择文件（支持大文件）")
    ctx.logger.info("已选择文件：%s，等待上传完成", video.name)
    try:
        ensure_title(ctx, copy_text)
    except Exception as exc:
        ctx.logger.warning("上传过程中填标题失败（稍后重试）：%s", exc)
    wait_upload_ready(ctx, video.name)
    run_extra_actions(ctx)
    uncheck_download_permission(ctx)
    # 作者声明和定时发布都在这里按“每一条视频”的配置执行；
    # 任何一项校验失败都会抛出 SkipVideo，绝不带着错误设置点击发布。
    apply_publish_options(ctx, data)
    if ctx.dry_run:
        return None
    try:
        if not ensure_title(ctx, copy_text):
            raise UncertainResult("标题没有完整填入（可能被页面截断），为避免发出错误标题，已停止这一条")
    except UncertainResult:
        raise
    except Exception as exc:
        raise UncertainResult("发布前无法确认标题是否完整：%s" % exc)
    # 页面在上传/处理完成后会重绘，可能把「允许下载此作品」重新勾上，所以发布前再确认一次
    uncheck_download_permission(ctx)
    click_publish(ctx)
    return wait_publish_result(ctx, copy_text)


def run_account(ctx: CreatorContext) -> Dict[str, Any]:
    """跑完一个账号的所有视频。"""
    account_name = ctx.account.get("name") or "未命名账号"
    wait_seconds = float(ctx.creator.get("post_publish_wait_seconds", 10))
    result = {
        "account": account_name,
        "published": 0,
        "skipped": 0,
        "skipped_videos": [],
        "scheduled": [],
        "dry_run": ctx.dry_run,
    }
    ensure_upload_page(ctx)
    for index, video in enumerate(ctx.videos):
        if ctx.bridge.stopped():
            raise StoppedByUser("用户停止运行")
        copy_text = ctx.copies[index]
        video_path = str(video)
        setting = dict(ctx.video_settings[index] if index < len(ctx.video_settings) else {})
        publish_at = normalize_publish_at(setting.get("publish_at"))
        publish_mode = "定时发布" if publish_at else "立即发布"
        ctx.state.item(account_name, index, video.name, copy_text, video_path)
        ctx.state.set_transient(
            account_name,
            index,
            path=video_path,
            _author_statement=str(setting.get("author_statement") or ""),
        )
        if ctx.state.is_published_path(account_name, video_path):
            ctx.logger.info("第 %d 条已发布过（同一个文件），自动跳过：%s", index + 1, video.name)
            result["skipped"] += 1
            continue
        started = time.time()
        ctx.bridge.status("[%s] 第 %d/%d 条：%s" % (account_name, index + 1, len(ctx.videos), video.name))
        ctx.logger.info("开始第 %d/%d 条：%s", index + 1, len(ctx.videos), video.name)
        attempts = 0
        skip_reason = ""
        while True:
            attempts += 1
            try:
                work_url = publish_once(ctx, video, copy_text, setting)
                break
            except SkipVideo as exc:
                skip_reason = str(exc) or "这条视频的发布设置没有通过校验"
                break
            except DefiniteFailure as exc:
                if attempts >= 3:
                    raise
                ctx.logger.warning(
                    "第 %d 条失败（%s），刷新页面后重试（第 %d 次尝试）", index + 1, exc, attempts
                )
                time.sleep(3)
                try:
                    ctx.page.reload(wait_until="domcontentloaded", timeout=60000)
                    ctx.page.wait_for_timeout(2000)
                except Exception as exc2:
                    ctx.logger.info("刷新页面失败（继续尝试重新打开）：%s", exc2)
                ensure_upload_page(ctx, force_navigate=True)
            except (UncertainResult, PageChanged, LoginRequired, StoppedByUser) as exc:
                shot = ctx.bridge.shot(ctx.page, "%s_%02d_异常" % (account_name, index + 1))
                ctx.state.mark(
                    account_name,
                    index,
                    path=video_path,
                    publish_status="发布结果不确定",
                    seconds=int(time.time() - started),
                    note="%s；截图 %s" % (exc, shot or "无"),
                )
                ctx.logger.error("第 %d 条异常，已停止该账号：%s", index + 1, exc)
                if isinstance(exc, LoginRequired) and ctx.creator.get("manual_rescue", True):
                    ctx.bridge.confirm(
                        "需要重新登录",
                        "这个账号的登录态已失效。请在该 Chrome 窗口扫码登录，登录完成后重新启动这个账号，"
                        "脚本会从断点继续，不会重复发布。",
                    )
                raise
        if skip_reason:
            ctx.bridge.status("[%s] 第 %d 条未发布，已跳过" % (account_name, index + 1))
            ctx.logger.warning("第 %d 条未发布，已跳过：%s", index + 1, skip_reason)
            shot = ctx.bridge.shot(ctx.page, "%s_%02d_发布设置未通过" % (account_name, index + 1))
            ctx.state.mark(
                account_name,
                index,
                path=video_path,
                publish_status=("演练未发布" if ctx.dry_run else "已跳过"),
                publish_mode=publish_mode,
                publish_at=publish_at,
                skip_reason=skip_reason,
                seconds=int(time.time() - started),
                note=(
                    "演练未通过：%s；截图 %s" % (skip_reason, shot or "无")
                    if ctx.dry_run
                    else "%s；截图 %s" % (skip_reason, shot or "无")
                ),
            )
            result["skipped_videos"].append(
                {"index": index, "file": video.name, "reason": skip_reason}
            )
            if not ctx.dry_run:
                # 已经上传但没发布，页面还停在编辑态；刷新回干净上传页再处理下一条。
                try:
                    ensure_upload_page(ctx, force_navigate=True)
                except Exception as exc:
                    ctx.logger.warning("跳过本条后刷新上传页失败：%s", exc)
            continue
        if ctx.dry_run:
            shot = ctx.bridge.shot(ctx.page, "%s_%02d_演练" % (account_name, index + 1))
            ctx.state.mark(
                account_name,
                index,
                path=video_path,
                publish_status="演练未发布",
                publish_mode=publish_mode,
                publish_at=publish_at,
                scheduled_status="演练",
                seconds=int(time.time() - started),
                note="演练模式未点击发布；发布设置=%s；截图 %s"
                % (publish_mode, shot or "无"),
            )
            ctx.logger.info("演练完成（未发布）：%s", video.name)
            back_to_upload(ctx)
            continue
        scheduled_note = ""
        if publish_at:
            scheduled_note = "定时发布：%s" % publish_at.replace("T", " ")[:16]
        ctx.state.mark(
            account_name,
            index,
            path=video_path,
            publish_status="已发布",
            work_url=work_url or "",
            publish_mode=publish_mode,
            publish_at=publish_at,
            scheduled_status=("已提交" if publish_at else ""),
            seconds=int(time.time() - started),
            note=scheduled_note,
        )
        result["published"] += 1
        if publish_at:
            result["scheduled"].append(
                {
                    "index": index,
                    "file": video.name,
                    "copy": copy_text,
                    "publish_at": publish_at,
                }
            )
        ctx.logger.info("第 %d 条完成，等待 %.0f 秒后继续下一条", index + 1, wait_seconds)
        time.sleep(wait_seconds)
        back_to_upload(ctx)
    return result
