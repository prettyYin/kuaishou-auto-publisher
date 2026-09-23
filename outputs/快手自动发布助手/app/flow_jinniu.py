# -*- coding: utf-8 -*-
"""阶段二：磁力金牛——把素材名改回视频文件名。

两种方式：
  1) 按标题搜索（推荐）：用广告语在素材库里搜索，命中的那条素材改名为对应文件名；
  2) 按上传时间倒序：取当日新增的 N 条素材（金牛默认最新在最上面），
     与文件夹里的视频顺序**倒序**一一对应后批量改名。
"""
from __future__ import annotations

import time
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import config as cfgmod
from .errors import PageChanged, StoppedByUser
from .videometa import duration_seconds, extract_duration_seconds
from .selectors import (
    Selectors,
    build_locator,
    click_any,
    fill_any,
    find_any,
    find_list,
    set_text,
)

FALLBACK: Dict[str, List[Dict[str, Any]]] = {
    "search_input": [
        {"placeholder": "请输入素材名称"},
        {"css": "input.ant-input[placeholder*='素材名称']"},
        {"placeholder": "搜索素材名称"},
        {"placeholder": "搜索"},
    ],
    "search_box": [
        {"css": "[class*='inputWrapper'] input.ant-input"},
        {"css": "[class*='inputWrapper'] input"},
        {"css": "input.ant-input[placeholder*='素材名称']"},
        {"css": "input.ant-input[placeholder*='视频ID']"},
        {"css": "input[placeholder*='素材']"},
    ],
    "search_button": [
        {"css": "[class*='inputWrapper'] .anticon-search"},
        {"css": "svg[data-icon='search']"},
        {"css": "span[aria-label='search']"},
        {"text": "查询"},
        {"text": "搜索"},
        {"role": "button", "name": "查询"},
    ],
    "filter_field_select": [
        {"css": "div.ant-select:has(+ div [class*='inputWrapper'])"},
        {"css": "div.ant-select-selector:has(#rc_select_0)"},
        {"css": "div.ant-select-selector:has(#rc_select_0) .ant-select-selection-item"},
        {"css": "input#rc_select_0"},
    ],
    "filter_field_selected": [
        {"css": "div.ant-select:has(+ div [class*='inputWrapper']) .ant-select-selection-item"},
        {"css": "div.ant-select-selector:has(#rc_select_0) .ant-select-selection-item"},
        {"css": ".ant-select-selection-item[title='素材名称']"},
    ],
    "filter_field_option": [
        {"css": "div.ant-select-dropdown:not([class*='hidden']) div.ant-select-item-option[title='素材名称']"},
        {"css": "div.ant-select-dropdown:not([class*='hidden']) div.ant-select-item-option[title='素材名称'] div"},
        {"text": "素材名称", "exact": True},
    ],
    "row_thumbnail": [
        {"css": "[class*='photo-info-cover']"},
        {"css": "[class*='photo-info-cover'] img"},
        {"css": "img[class*='cover']"},
        {"css": "[class*='videoCover'] img"},
    ],
    "list_scroll": [
        {"css": "[class*='fixedDataTableLayout_body']"},
        {"css": "[class*='public_fixedDataTable_body']"},
        {"css": "[class*='fixedDataTableLayout_rowsContainer']"},
    ],
    "column_settings_button": [
        {"css": "div.kcfe-ad-columns-filter"},
        {"css": "[class*='columns-filter']:not([class*='modal'])"},
    ],
    "column_dialog": [
        {"css": ".ant-modal-content:has-text('自定义列表')"},
        {"css": "[class*='columns-filter-modal-body']"},
    ],
    "column_duration_checkbox": [
        {"css": "label.ant-checkbox-wrapper:has-text('视频时长') input.ant-checkbox-input"},
        {"css": "label:has-text('视频时长') input[type=checkbox]"},
    ],
    "column_confirm_button": [
        {"css": ".ant-modal-footer button.ant-btn-primary"},
        {"text": "确定"},
    ],
    "popup_close": [
        {"css": "button.ant-modal-close"},
        {"css": ".ant-modal-close-x"},
        {"css": ".ant-notification-notice-close"},
        {"css": ".ant-drawer-close"},
        # 金牛活动推荐弹窗不是标准 antd 关闭按钮，而是自定义的右下角 X 图标
        {"css": ".ant-modal-wrap:not([style*='display: none']) [data-adview='true'] [class*='icon___']:last-child"},
        {"css": ".ant-modal-wrap:not([style*='display: none']) [data-adview='true'] svg"},
        {"css": ".ant-modal-wrap:not([style*='display: none']) [class*='modalWrap'] [class*='icon___']"},
    ],
    "preview_video": [
        {"css": ".ant-modal-body video"},
        {"css": "video.comp-video"},
        {"css": "video"},
    ],
    "preview_close": [
        {"css": ".ant-modal-close"},
        {"css": "[aria-label='Close']"},
        {"css": "[class*='closeIcon']"},
    ],
    "list_scroll_alt": [
        {"css": "[class*='fixedDataTableLayout_rowsContainer']"},
        {"css": "[class*='public_fixedDataTable_main']"},
        {"css": ".ant-table-body"},
    ],
    "account_chooser": [
        {"css": ".ant-modal-content:has-text('选择账户')"},
        {"css": "[class*='ant-modal']:has-text('选择账户')"},
        {"css": "[role=dialog]:has-text('选择账户')"},
    ],
    "account_chooser_row": [
        {"css": ".ant-table-row"},
        {"css": "tbody tr"},
    ],
    "account_chooser_enter": [
        {"text": "进入"},
        {"css": "a:has-text('进入')"},
        {"css": "button:has-text('进入')"},
    ],
    "page_size_select": [
        {"css": "[class*='ant-pagination-options'] .ant-select-selector"},
        {"css": "[class*='ant-pagination-options'] .ant-select"},
    ],
    "page_size_option": [
        {"css": "div.ant-select-dropdown:not([class*='hidden']) div.ant-select-item-option:has-text('100')"},
        {"css": "div.ant-select-dropdown:not([class*='hidden']) div.ant-select-item-option:has-text('50')"},
        {"text": "100 条/页"},
    ],
    "material_row": [
        {"css": "[class*='fixedDataTableLayout_body'] [class*='rowWrapper']"},
        {"css": "div[class*='rowWrapper']:not(:has([class*='fixedDataTableLayout_header']))"},
        {"css": "[class*='fixedDataTableRowLayout_rowWrapper']"},
        {"css": "tbody tr"},
        {"css": "[class*=ant-table-row]"},
        {"css": "[class*=table-row]"},
        {"css": "[class*=material-item]"},
        {"css": "[class*=card]"},
    ],
    "material_checkbox": [
        {"css": "input[type=checkbox]"},
        {"css": "[class*=checkbox]"},
    ],
    "material_name_cell": [
        {"css": "[class*=name]"},
        {"css": "td"},
    ],
    "batch_rename_button": [
        {"text": "修改视频名称"},
        {"text": "批量修改视频名称"},
        {"text": "批量改名"},
        {"text": "批量重命名"},
        {"text": "批量编辑"},
        {"text": "重命名"},
        {"text": "改名"},
    ],
    "batch_bar": [
        {"css": "[class*='batchEditBar']"},
        {"text": "已选"},
    ],
    "batch_bar_close": [
        {"css": "[class*='batchEditBar'] [class*='closeIcon']"},
        {"css": "[class*='batchEditorContainer'] [class*='closeIcon']"},
        {"css": "[aria-label='system-close-medium-line']"},
    ],
    "select_all_checkbox": [
        {"css": "[class*='fixedDataTableLayout_header'] input.ant-checkbox-input"},
        {"css": "[class*='tableHeader'] input[type=checkbox]"},
        {"css": "thead input[type=checkbox]"},
    ],
    "row_name_target": [
        {"css": "[class*='videoName']"},
        {"css": "[class*='name']"},
        {"css": "[class*='title']"},
    ],
    "row_rename_pencil": [
        {"css": "[class*='editIcon']"},
        {"css": "[class*='hoverEdit']"},
        {"css": "[aria-label*='edit']"},
        {"css": "svg[data-icon*='edit']"},
        {"css": "[class*='edit']"},
    ],
    "single_rename_button": [
        {"text": "改名"},
        {"text": "重命名"},
        {"text": "编辑"},
    ],
    "rename_dialog": [
        {"css": "[role=dialog]"},
        {"css": ".ant-modal-content"},
        {"css": "[class*='ant-modal']"},
        {"css": "[class*=ant-modal]"},
        {"css": "[class*=modal-content]"},
        {"css": "[class*=drawer]"},
    ],
    "rename_row_inputs": [
        {"css": ".ant-modal-body .ant-table-body input.ant-input"},
        {"css": ".ant-modal-body input.ant-input"},
        {"css": "input[placeholder*='视频名称']"},
    ],
    "rename_textarea": [{"css": "textarea"}],
    "rename_name_input": [
        {"placeholder": "请输入素材名"},
        {"placeholder": "请输入视频名称"},
        {"placeholder": "素材名"},
        {"placeholder": "名称"},
        {"css": "input[type=text]"},
    ],
    "rename_confirm_button": [
        {"css": ".ant-modal-footer button.ant-btn-primary"},
        {"text": "确定"},
        {"text": "确认"},
        {"text": "保存"},
        {"text": "提交"},
    ],
}


class JinniuContext:
    def __init__(self, bridge, page, cfg, account, videos, copies, state, logger) -> None:
        self.bridge = bridge
        self.page = page
        self.cfg = cfg
        self.account = account
        self.videos = videos
        self.copies = list(copies or [])
        self.state = state
        self.logger = logger
        self.selectors = Selectors.load()
        self.jinniu = cfg.get("jinniu", {})


def _cands(ctx: JinniuContext, key: str) -> List[Dict[str, Any]]:
    return ctx.selectors.merged("jinniu", key, FALLBACK[key])


def _settle(ctx: JinniuContext) -> None:
    ctx.page.wait_for_timeout(int(float(ctx.jinniu.get("settle_wait_seconds", 5)) * 1000))


def _account_name(ctx: JinniuContext) -> str:
    return ctx.account.get("name") or "未命名账号"


def mark_state(ctx: JinniuContext, index: int, **fields) -> None:
    """记录改名状态，并带上完整路径（状态记录以「账号+路径」为键）。"""
    try:
        path = str(ctx.videos[index]) if 0 <= index < len(ctx.videos) else ""
        ctx.state.mark(_account_name(ctx), index, path=path, **fields)
    except Exception as exc:
        # 记录失败绝不能中断改名流程
        try:
            ctx.logger.warning("记录状态失败（不影响流程）：%s", exc)
        except Exception:
            pass


def ensure_library_page(ctx: JinniuContext) -> None:
    ctx.logger.info("准备金牛素材库页面…")
    url = library_url(ctx)
    host = url.split("//")[-1].split("/")[0] if url else ""
    if url and host and host not in (ctx.page.url or ""):
        ctx.logger.info("打开磁力金牛视频库：%s", url)
        ctx.page.goto(url, wait_until="domcontentloaded", timeout=90000)
        ctx.page.wait_for_timeout(2500)
    # 不同账号的 accountId 不同，金牛会弹「选择账户」，自动选一个并把地址记下来
    account_id = dismiss_account_chooser(ctx)
    if account_id:
        new_url = ctx.page.url or ""
        ctx.account["jinniu_video_library_url"] = new_url
        if not str(ctx.account.get("jinniu_account_id") or "").strip():
            ctx.account["jinniu_account_id"] = account_id
        try:
            cfgmod.save_config(ctx.cfg)
        except Exception:
            pass
        ctx.logger.info("已记录该账号的金牛素材库地址（账号 ID %s），下次直接进入", account_id)
        ctx.bridge.status("已记录账号 %s 的金牛地址，下次直接进入" % account_id)
    if find_list(ctx.page, _cands(ctx, "material_row"), min_count=1) is not None:
        ctx.logger.info("素材库页面就绪，正在调整列表显示…")
        dismiss_popups(ctx)
        ensure_page_size(ctx)
        ensure_duration_column(ctx)
        ctx.logger.info("列表已准备好")
        return
    answer = ctx.bridge.rescue(
        "需要你手动打开金牛素材库",
        "当前页面没找到素材列表。请在这个自动化浏览器窗口里打开\n"
        "「磁力金牛 → 视频库 / 素材库」列表页，然后再选择下面的一项。",
        ["已经打开好了，继续", "跳过这个账号", "停止运行"],
    )
    if answer == "跳过这个账号":
        raise StoppedByUser("用户选择跳过该账号")
    if answer == "停止运行":
        raise StoppedByUser("用户停止运行")
    if find_list(ctx.page, _cands(ctx, "material_row"), min_count=1) is None:
        raise PageChanged("页面上找不到素材列表")
    dismiss_popups(ctx)
    ensure_page_size(ctx)
    ensure_duration_column(ctx)


def _row_text(row) -> str:
    try:
        text = (row.inner_text() or "").strip()
    except Exception:
        text = ""
    if not text:
        try:
            locator = row.locator("[class*=name]")
            if locator.count() > 0:
                text = (locator.first.inner_text() or "").strip()
        except Exception:
            text = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[0] if lines else "")[:80]


def _rows(ctx: JinniuContext):
    return find_list(ctx.page, _cands(ctx, "material_row"), min_count=1)


def read_material_names(ctx: JinniuContext, count: int) -> List[str]:
    rows = _rows(ctx)
    if rows is None:
        return []
    names: List[str] = []
    for index in range(min(rows.count(), max(count, 1))):
        names.append(_row_text(rows.nth(index)))
    return names


def read_row_texts(ctx: JinniuContext, count: int) -> List[str]:
    """读取前 count 行的完整文字（用于取时长等信息）。"""
    rows = _rows(ctx)
    if rows is None:
        return []
    texts: List[str] = []
    for index in range(min(rows.count(), max(count, 1))):
        try:
            texts.append((rows.nth(index).inner_text() or "").replace("\n", " ").strip())
        except Exception:
            texts.append("")
    return texts


def read_rows_full(ctx: JinniuContext, limit: int = 300, probe: bool = False):
    """滚动列表把所有素材行读全（表格虚拟滚动，一屏只渲染几行）。

    返回 [(素材名, 创建时间戳 or None, 行全文, 时长 or None)]，按页面显示顺序。
    """
    from datetime import datetime as _dt

    try:
        ensure_duration_column(ctx)
    except Exception:
        pass
    collected = {}
    order: List[str] = []
    scroll = find_any(ctx.page, _cands(ctx, "list_scroll"), timeout=4)
    # 表格是内部滚动的：必须把鼠标移到表格上再滚，否则滚的是页面
    if scroll is not None:
        try:
            box = scroll.bounding_box()
            if box:
                ctx.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        except Exception:
            pass

    def take_row(index: int) -> None:
        """读取当前渲染出来的第 index 行（必要时当场量时长）。"""
        rows_now = _rows(ctx)
        if rows_now is None or index >= rows_now.count():
            return
        try:
            text = (rows_now.nth(index).inner_text() or "").replace("\n", " ").strip()
        except Exception:
            text = ""
        if not text:
            return
        key = text[:120]
        if key in collected:
            return
        name = text.split("ID:")[0].strip()[:80] or text[:80]
        created = None
        match = _CREATE_RE.search(text)
        if match:
            try:
                created = _dt(*[int(item) for item in match.groups()]).timestamp()
            except Exception:
                created = None
        # 页面上有「视频时长」列，直接从这一行的文字里读，不用打开预览
        duration = extract_duration_seconds(text)
        if duration is None and probe:
            try:
                duration = probe_row_duration(ctx, index)
            except Exception:
                duration = None
        collected[key] = (name, created, text, duration)
        order.append(key)

    for _ in range(15):
        rows = _rows(ctx)
        if rows is not None:
            for index in range(rows.count()):
                take_row(index)
                if len(order) >= limit:
                    break
        if len(order) >= limit or scroll is None:
            if len(order) >= limit:
                break
        # 表格内部滚动一屏
        if scroll is not None:
            try:
                before_top = scroll.evaluate("el => el.scrollTop")
                scroll.evaluate("el => el.scrollTop = el.scrollTop + el.clientHeight * 0.8")
                ctx.page.wait_for_timeout(700)
                after_top = scroll.evaluate("el => el.scrollTop")
                if after_top != before_top:
                    continue
            except Exception:
                pass
        try:
            at_end = (
                scroll.evaluate("el => el.scrollTop + el.clientHeight >= el.scrollHeight - 6")
                if scroll is not None
                else True
            )
        except Exception:
            at_end = True
        if at_end:
            # 表格自身滚不动时，改用滚动整个页面（有些版本是页面在滚）
            try:
                before = len(order)
                ctx.page.mouse.wheel(0, 700)
                ctx.page.wait_for_timeout(600)
                rows = _rows(ctx)
                grown = False
                if rows is not None:
                    for index in range(rows.count()):
                        before_count = len(order)
                        take_row(index)
                        if len(order) > before_count:
                            grown = True
                if not grown and len(order) == before:
                    break
                continue
            except Exception:
                break
        try:
            scroll.evaluate("el => el.scrollTop = el.scrollTop + el.clientHeight * 0.85")
        except Exception:
            break
        ctx.page.wait_for_timeout(600)
    try:
        if scroll is not None:
            scroll.evaluate("el => el.scrollTop = 0")
            ctx.page.wait_for_timeout(500)
    except Exception:
        pass
    return [collected[key] for key in order]


def batch_bar_count(ctx: JinniuContext) -> int:
    """读取批量操作栏上的「已选 N 个视频」。"""
    bar = find_any(ctx.page, _cands(ctx, "batch_bar"), timeout=4)
    if bar is None:
        return 0
    try:
        numbers = re.findall(r"\d+", bar.inner_text() or "")
        return int(numbers[0]) if numbers else 0
    except Exception:
        return 0


def select_all_rows(ctx: JinniuContext) -> int:
    """勾选表头的全选框，一次选中当前页所有素材，返回已选数量。"""
    header = find_any(ctx.page, _cands(ctx, "select_all_checkbox"), timeout=4)
    if header is None:
        ctx.logger.info("没找到表头的全选框，改用逐行勾选")
        return 0
    try:
        if not header.is_checked():
            try:
                header.check(timeout=6000)
            except Exception:
                header.check(timeout=6000, force=True)
        ctx.page.wait_for_timeout(1500)
    except Exception as exc:
        ctx.logger.warning("全选失败：%s", exc)
        return 0
    return batch_bar_count(ctx)


def apply_batch_rename(ctx: JinniuContext, targets: Sequence[str]) -> bool:
    """在已勾选的状态下：点「修改视频名称」→ 逐行填 → 确定。"""
    dismiss_popups(ctx)
    try:
        click_any(ctx.page, _cands(ctx, "batch_rename_button"), timeout=8)
    except Exception as exc:
        ctx.logger.warning("找不到「修改视频名称」入口：%s", exc)
        return False
    ctx.page.wait_for_timeout(1200)
    if not _rename_dialog(ctx, targets):
        ctx.logger.warning("改名弹窗里没识别到输入框")
        return False
    if not _confirm_dialog(ctx):
        ctx.logger.warning("改名弹窗里没找到确定按钮")
        return False
    _settle(ctx)
    clear_selection(ctx)
    return True


def rename_material_by_name(ctx: JinniuContext, material_name: str, target_file: str) -> bool:
    """在列表里按素材名找到这一条（必要时滚动），勾选它并改名为 target_file。"""
    for _ in range(15):
        rows = _rows(ctx)
        if rows is not None:
            for index in range(rows.count()):
                row = rows.nth(index)
                try:
                    text = row.inner_text() or ""
                except Exception:
                    text = ""
                head = material_name[:14]
                if head and head in text:
                    ok = False
                    try:
                        box = find_any(row, _cands(ctx, "material_checkbox"), timeout=2)
                        if box is not None:
                            if not box.is_checked():
                                try:
                                    box.check(timeout=5000)
                                except Exception:
                                    box.check(timeout=5000, force=True)
                            ctx.page.wait_for_timeout(600)
                            bar = find_any(ctx.page, _cands(ctx, "batch_bar"), timeout=4)
                            selected_now = 0
                            if bar is not None:
                                numbers = re.findall(r"\d+", bar.inner_text() or "")
                                selected_now = int(numbers[0]) if numbers else 0
                            if selected_now != 1:
                                ctx.logger.warning(
                                    "勾选数量不是 1（当前 %d 条），先取消全部勾选再重试这一条", selected_now
                                )
                                clear_selection(ctx)
                                return False
                            click_any(ctx.page, _cands(ctx, "batch_rename_button"), timeout=8)
                            ctx.page.wait_for_timeout(1000)
                            ok = _rename_dialog(ctx, [target_file]) and _confirm_dialog(ctx)
                            _settle(ctx)
                            clear_selection(ctx)
                    except Exception as exc:
                        ctx.logger.warning("改名「%s」时出错：%s", material_name[:20], exc)
                    return ok
        scroll = find_any(ctx.page, _cands(ctx, "list_scroll"), timeout=3)
        if scroll is None:
            return False
        try:
            at_end = scroll.evaluate("el => el.scrollTop + el.clientHeight >= el.scrollHeight - 6")
            if at_end:
                return False
            scroll.evaluate("el => el.scrollTop = el.scrollTop + el.clientHeight * 0.85")
        except Exception:
            return False
        ctx.page.wait_for_timeout(600)
    return False


_CREATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})[\sT]+(\d{1,2}):(\d{2}):(\d{2})")
_ACCOUNT_ID_RE = re.compile(r"__accountId__=(\d+)")
_TOTAL_RE = re.compile(r"共\s*([\d,，]+)\s*(?:条|个)")


def read_total_count(ctx: JinniuContext) -> Optional[int]:
    """读取列表底部的「共 N 条」——虚拟滚动时页面上只会渲染部分行，这个计数才准。"""
    try:
        texts = ctx.page.evaluate(
            "() => {const nodes=[...document.querySelectorAll('[class*=pagination], [class*=Pagination], [class*=table] ')];"
            " const out=[]; for (const n of nodes.slice(0,60)) { const t=(n.innerText||'').trim(); if (t && t.length < 200) out.push(t);} return out;}"
        )
    except Exception:
        texts = []
    for text in texts or []:
        match = _TOTAL_RE.search(str(text))
        if match:
            try:
                return int(match.group(1).replace(",", "").replace("，", ""))
            except Exception:
                continue
    return None


def extract_account_id(url: str) -> str:
    """从金牛地址里取出账号 ID。"""
    match = _ACCOUNT_ID_RE.search(url or "")
    return match.group(1) if match else ""


def library_url(ctx: JinniuContext) -> str:
    """这个账号自己的素材库地址：公共地址 + 该账号填写的 accountId。"""
    return cfgmod.build_library_url(ctx.cfg, ctx.account)


def dismiss_account_chooser(ctx: JinniuContext) -> str:
    """金牛弹出「选择账户」时，选一个并返回跳转后的账号 ID。"""
    dialog = find_any(ctx.page, _cands(ctx, "account_chooser"), timeout=4)
    if dialog is None:
        return ""
    ctx.logger.info("金牛弹出了「选择账户」，自动选一个进入")
    rows = find_list(dialog, _cands(ctx, "account_chooser_row"), min_count=1)
    picked = None
    if rows is not None:
        current_index = None
        for index in range(min(rows.count(), 40)):
            try:
                text = rows.nth(index).inner_text() or ""
            except Exception:
                text = ""
            if "当前" in text:
                current_index = index
                break
        position = current_index if current_index is not None else 0
        try:
            picked = find_any(rows.nth(position), _cands(ctx, "account_chooser_enter"), timeout=3)
            ctx.logger.info("选择第 %d 行的账户%s", position + 1, "（标记为当前）" if current_index is not None else "（默认第一个）")
        except Exception:
            picked = None
    if picked is None:
        enter = find_any(ctx.page, _cands(ctx, "account_chooser_enter"), timeout=4)
        if enter is None:
            ctx.logger.warning("没找到「进入」按钮，先关掉这个浮层")
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
            return ""
        picked = enter
    try:
        picked.click(timeout=8000)
    except Exception:
        try:
            picked.click(timeout=8000, force=True)
        except Exception as exc:
            ctx.logger.warning("点「进入」失败：%s", exc)
            return ""
    ctx.page.wait_for_timeout(3500)
    return extract_account_id(ctx.page.url or "")

_PUNCTUATION = set("，。！？；：、,.!?;:~…—－-—　 \t\n\r（）()【】[]《》<>\"'“”‘’#@￥$%^&*+=|\\/")


def build_fallback_keyword(text: str, min_chars: int = 12) -> str:
    """构造兜底查询关键词：从 min_chars 个字开始，一直延伸到下一个标点符号之前。

    平台按分词匹配，关键词里混进标点容易查不到，所以在标点处断开。
    """
    text = (text or "").strip()
    if len(text) <= min_chars:
        return text
    if text[min_chars] in _PUNCTUATION:
        return text[:min_chars]
    for index in range(min_chars, len(text)):
        if text[index] in _PUNCTUATION:
            return text[:index]
    return text


def read_row_creations(ctx: JinniuContext, count: int) -> List[Optional[float]]:
    """读取每行的创建时间（时间戳）；读不到的返回 None。"""
    from datetime import datetime as _dt

    result: List[Optional[float]] = []
    for text in read_row_texts(ctx, count):
        match = _CREATE_RE.search(text or "")
        if not match:
            result.append(None)
            continue
        try:
            parts = [int(item) for item in match.groups()]
            result.append(_dt(*parts).timestamp())
        except Exception:
            result.append(None)
    return result


def build_targets_for_group(
    ctx: JinniuContext, group: Dict[str, Any], names: Sequence[str], list_order: str
) -> List[str]:
    """决定每一行该填哪个文件名。

    优先用「创建时间」对齐：最早创建的素材 = 你上传的第一个视频（与列表显示顺序无关）。
    读不到创建时间时，退回「列表顺序 ↔ 文件夹顺序」的规则。
    """
    files = [file_name for _, file_name in group["items"]]
    count = min(len(names), len(files))
    if not count:
        return []
    if count > 1:
        creations = read_row_creations(ctx, len(names))
        if all(item is not None for item in creations[:count]):
            order = sorted(range(count), key=lambda index: creations[index])
            targets = [""] * count
            for position, file_name in zip(order, files[:count]):
                targets[position] = file_name
            ctx.logger.info(
                "按「创建时间」对齐 %d 条（第 %d 行是最早创建的，对应文件夹里第 1 条视频）",
                count,
                order[0] + 1,
            )
            return targets
        ctx.logger.info("读不到创建时间，改用「列表顺序 ↔ 文件夹倒序」的规则对应")
    return targets_for_rows(names, group, list_order)


def match_targets_two_level(
    ctx: JinniuContext,
    group: Dict[str, Any],
    durations: Sequence[Optional[float]],
    creations: Sequence[Optional[float]] = None,
):
    """两级配对：先按视频时长；时长相同（或读不到时长）的，再按上传先后顺序对应文件夹顺序。

    返回每行的目标文件名（None = 没配上）。规则：
    1) 某一行素材的时长在文件夹里只有唯一一个视频匹配 → 直接配对；
    2) 该时长对应文件夹里多个视频（或这一行读不到时长）→ 这些行按"金牛创建时间从早到晚"排序，
       依次对应"文件夹里剩下的视频（按文件名排序）"。
    """
    folder_files = [(index, ctx.videos[index]) for index, _ in group["items"] if index < len(ctx.videos)]
    local = {index: duration_seconds(str(video)) for index, video in folder_files}
    tolerance = float(ctx.jinniu.get("duration_tolerance_seconds", 1) or 1)
    result: List[Optional[str]] = [None] * len(durations)
    used_files = set()
    pending: List[tuple] = []

    for position, shown in enumerate(durations):
        if shown is None:
            pending.append((position, None))
            continue
        candidates = [
            index
            for index, _video in folder_files
            if index not in used_files
            and local.get(index)
            and abs(float(local[index]) - float(shown)) <= tolerance
        ]
        if len(candidates) == 1:
            used_files.add(candidates[0])
            result[position] = ctx.videos[candidates[0]].name
        else:
            pending.append((position, candidates))

    remaining = [(index, video) for index, video in folder_files if index not in used_files]
    if pending and remaining:
        def row_order(item):
            position = item[0]
            created = creations[position] if creations and position < len(creations) else None
            return (0, created, position) if created else (1, 0, position)

        paired = 0
        for position, _candidates in sorted(pending, key=row_order):
            if paired >= len(remaining):
                break
            index, video = remaining[paired]
            result[position] = video.name
            paired += 1
        if paired:
            ctx.logger.info(
                "有 %d 条素材时长相同或读不到时长，已按「上传先后 ↔ 文件夹顺序」依次配对", paired
            )
    return result


def match_targets_by_duration(ctx: JinniuContext, group: Dict[str, Any], durations: Sequence[Optional[float]]):
    """按每条素材的时长，匹配文件夹里时长最接近的视频；返回每行的目标文件名（None=没匹配上）。"""
    folder_files = [(index, ctx.videos[index]) for index, _ in group["items"] if index < len(ctx.videos)]
    local = {index: duration_seconds(str(video)) for index, video in folder_files}
    tolerance = float(ctx.jinniu.get("duration_tolerance_seconds", 1) or 1)
    used = set()
    result: List[Optional[str]] = []
    for shown in durations:
        if shown is None:
            result.append(None)
            continue
        best = None
        best_diff = None
        for index, video in folder_files:
            if index in used:
                continue
            value = local.get(index)
            if not value:
                continue
            diff = abs(float(value) - float(shown))
            if diff <= tolerance and (best_diff is None or diff < best_diff):
                best_diff, best = diff, (index, video.name)
        if best is None:
            result.append(None)
        else:
            used.add(best[0])
            result.append(best[1])
    return result


def resolve_by_duration(ctx: JinniuContext, group: Dict[str, Any], targets: Sequence[str]):
    """按时长把每一行重新对应到文件夹里的某个视频。

    返回 (新目标文件名列表, 说明列表)；新目标为 None 表示这一行在文件夹里找不到时长匹配的视频。
    """
    folder_files = [(index, ctx.videos[index]) for index, _ in group["items"] if index < len(ctx.videos)]
    local = {index: duration_seconds(str(video)) for index, video in folder_files}
    tolerance = float(ctx.jinniu.get("duration_tolerance_seconds", 1) or 1)
    used = set()
    result: List[Optional[str]] = []
    notes: List[str] = []
    for position in range(len(targets)):
        shown = probe_row_duration(ctx, position)
        if shown is None:
            # 读不到时长时不能拿"当前素材名"当目标，否则会白改一遍
            result.append(None)
            notes.append("读不到这条素材的时长（预览没加载出来），先跳过")
            continue
        match = None
        for index, video in folder_files:
            if index in used:
                continue
            value = local.get(index)
            if value and abs(float(value) - float(shown)) <= tolerance:
                match = (index, video.name)
                break
        if match is None:
            result.append(None)
            notes.append("金牛素材 %.0f 秒，在文件夹里找不到时长一致的视频" % shown)
            continue
        used.add(match[0])
        if match[1] != targets[position]:
            notes.append("按时长重新对应：金牛 %.0f 秒 → %s（原先对应 %s）" % (shown, match[1], targets[position]))
        else:
            notes.append("")
        result.append(match[1])
    return result, notes


def probe_row_duration(ctx: JinniuContext, row_index: int) -> Optional[float]:
    """点开素材缩略图，从预览播放器里读出这条素材的时长（秒）。"""
    rows = _rows(ctx)
    if rows is None or row_index >= rows.count():
        return None
    row = rows.nth(row_index)
    thumb = find_any(row, _cands(ctx, "row_thumbnail"), timeout=4)
    if thumb is None:
        return None
    try:
        thumb.click(timeout=8000)
    except Exception:
        try:
            thumb.click(timeout=8000, force=True)
        except Exception as exc:
            ctx.logger.info("点不开第 %d 行的素材预览：%s", row_index + 1, exc)
            return None
    duration: Optional[float] = None
    try:
        video = find_any(ctx.page, _cands(ctx, "preview_video"), timeout=12)
        if video is not None:
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    value = video.evaluate(
                        "el => (el.duration && isFinite(el.duration) && el.duration > 0) ? el.duration : null"
                    )
                except Exception:
                    value = None
                if value:
                    duration = float(value)
                    break
                try:
                    video.evaluate("el => { if (el.paused && el.readyState < 2) { el.load && el.load(); } }")
                except Exception:
                    pass
                ctx.page.wait_for_timeout(500)
        if duration is None:
            ctx.logger.info("第 %d 条素材的预览没读出时长（可能没加载出来）", row_index + 1)
    finally:
        close = find_any(ctx.page, _cands(ctx, "preview_close"), timeout=2)
        if close is not None:
            try:
                close.click(timeout=5000)
            except Exception:
                pass
        else:
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
        ctx.page.wait_for_timeout(600)
    return duration


def duration_check(ctx: JinniuContext, group: Dict[str, Any], names: Sequence[str], list_order: str):
    """逐行点开预览读素材时长，和本地视频时长比对；返回 {行号: (是否一致, 说明)}。"""
    report: Dict[int, tuple] = {}
    unknown = 0
    for position in range(len(names)):
        pair = item_for_row(group, position, list_order)
        if not pair:
            continue
        index, file_name = pair
        path = str(ctx.videos[index]) if index < len(ctx.videos) else ""
        local = duration_seconds(path) if path else None
        shown = probe_row_duration(ctx, position)
        if local is None or shown is None:
            unknown += 1
            report[position] = (True, "")
            continue
        diff = abs(float(local) - float(shown))
        report[position] = (
            diff <= 3,
            "%s 本地 %.0f 秒 / 金牛素材 %.0f 秒" % (file_name, local, shown),
        )
    if unknown:
        ctx.logger.info("有 %d 条读不到时长（本地或预览），这些不做时长校验", unknown)
    return report


def click_next_page(ctx: JinniuContext) -> bool:
    """点击分页的「下一页」。返回是否成功跳转。"""
    candidates = [
        {"css": "li[title='下一页'] button"},
        {"css": "button.ant-pagination-item-link:has(svg[data-icon='right'])"},
        {"css": "[class*='ant-pagination-next'] button"},
        {"css": "[class*='ant-pagination-next']"},
    ]
    for candidate in candidates:
        try:
            locator = build_locator(ctx.page, candidate)
            if locator.count() == 0:
                continue
            if not locator.is_enabled():
                return False
            locator.click(timeout=6000)
            ctx.logger.info("已翻到下一页")
            return True
        except Exception:
            continue
    return False


def dismiss_popups(ctx: JinniuContext, rounds: int = 5) -> int:
    """关掉挡在前面的弹窗（活动推荐、公告、提示等），返回关掉的数量。

    这些弹窗会盖住筛选字段/搜索框/批量栏，导致后面点不到元素而"卡住"。
    """
    closed = 0
    for _ in range(max(rounds, 1)):
        close = find_any(ctx.page, _cands(ctx, "popup_close"), timeout=2)
        if close is None:
            break
        clicked = False
        for force in (False, True):
            try:
                close.click(timeout=4000, force=force)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
        # 点完必须确认弹窗真的消失，不能假设 click 一定起作用
        gone = False
        for _ in range(8):
            ctx.page.wait_for_timeout(300)
            if find_any(ctx.page, _cands(ctx, "popup_close"), timeout=0.5) is None:
                gone = True
                break
        if not gone:
            try:
                ctx.page.keyboard.press("Escape")
            except Exception:
                pass
            ctx.page.wait_for_timeout(600)
            gone = find_any(ctx.page, _cands(ctx, "popup_close"), timeout=0.5) is None
        if not gone:
            ctx.logger.warning("弹窗没有真正关闭，后续可能需要人工处理")
            break
        closed += 1
    if closed:
        ctx.logger.info("已关闭 %d 个挡在前面的弹窗", closed)
    return closed


def ensure_duration_column(ctx: JinniuContext) -> bool:
    """确保列表里显示「视频时长」列（列被隐藏时自动打开，否则读不到时长）。"""
    for text in read_row_texts(ctx, 3):
        if extract_duration_seconds(text) is not None:
            return True
    ctx.logger.info("列表里没有「视频时长」列，正在自动打开…")
    trigger = find_any(ctx.page, _cands(ctx, "column_settings_button"), timeout=5)
    if trigger is None:
        ctx.logger.warning("找不到「自定义列表」入口，无法打开视频时长列")
        return False
    try:
        try:
            trigger.click(timeout=5000)
        except Exception:
            trigger.click(timeout=5000, force=True)
        ctx.page.wait_for_timeout(1000)
    except Exception as exc:
        ctx.logger.warning("打不开「自定义列表」：%s", exc)
        return False
    dialog = find_any(ctx.page, _cands(ctx, "column_dialog"), timeout=6)
    scope = dialog if dialog is not None else ctx.page
    box = find_any(scope, _cands(ctx, "column_duration_checkbox"), timeout=5)
    if box is None:
        ctx.logger.warning("「自定义列表」里没找到「视频时长」选项")
        try:
            ctx.page.keyboard.press("Escape")
        except Exception:
            pass
        return False
    try:
        if not box.is_checked():
            try:
                box.check(timeout=5000)
            except Exception:
                box.check(timeout=5000, force=True)
            ctx.page.wait_for_timeout(500)
    except Exception as exc:
        ctx.logger.warning("勾选「视频时长」失败：%s", exc)
    try:
        click_any(scope, _cands(ctx, "column_confirm_button"), timeout=8)
    except Exception:
        try:
            click_any(ctx.page, _cands(ctx, "column_confirm_button"), timeout=6)
        except Exception as exc:
            ctx.logger.warning("点「确定」失败：%s", exc)
            return False
    ctx.page.wait_for_timeout(1800)
    ok = any(extract_duration_seconds(text) is not None for text in read_row_texts(ctx, 3))
    ctx.logger.info("「视频时长」列已打开" if ok else "打开了自定义列表，但仍读不到视频时长")
    return ok


def ensure_page_size(ctx: JinniuContext) -> None:
    """把列表改成每页 100 条，避免一页只渲染 10 行导致漏改。"""
    try:
        current = ctx.page.locator("[class*='ant-pagination-options'] .ant-select-selection-item").first.inner_text()
    except Exception:
        current = ""
    if current and "100" in current:
        return
    select = find_any(ctx.page, _cands(ctx, "page_size_select"), timeout=4)
    if select is None:
        return
    try:
        try:
            select.click(timeout=5000)
        except Exception:
            select.click(timeout=5000, force=True)
        ctx.page.wait_for_timeout(700)
        option = find_any(ctx.page, _cands(ctx, "page_size_option"), timeout=5)
        if option is None:
            ctx.logger.info("没找到「100 条/页」选项，保持默认每页条数")
            return
        try:
            option.click(timeout=5000)
        except Exception:
            option.click(timeout=5000, force=True)
        ctx.page.wait_for_timeout(1500)
        ctx.logger.info("已把列表改成每页 100 条（原为「%s」）", current or "默认")
    except Exception as exc:
        ctx.logger.info("切换每页条数失败（不影响改名）：%s", exc)


def fill_quiet(ctx: JinniuContext, candidates: Sequence[Dict[str, Any]], value: str) -> bool:
    """直接给输入框赋值，不触发页面滚动（避免搜索时上下翻动）。"""
    locator = find_any(ctx.page, candidates, timeout=6, need_visible=False)
    if locator is None:
        return False
    try:
        locator.evaluate(
            "(el, v) => {"
            "  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;"
            "  el.focus();"
            "  setter.call(el, v);"
            "  el.dispatchEvent(new Event('input', {bubbles: true}));"
            "  el.dispatchEvent(new Event('change', {bubbles: true}));"
            "}",
            value,
        )
    except Exception:
        return False
    # 赋值后回读确认真的写进去了（React 受控输入有时会回滚）
    try:
        current = locator.input_value() or ""
    except Exception:
        current = ""
    if value and value not in current:
        ctx.logger.info("直接赋值没生效（当前是「%s」），改用常规输入", current[:16])
        return False
    return True


def clear_selection(ctx: JinniuContext) -> bool:
    """关掉批量操作栏 / 取消所有勾选（它开着的时候会挡住搜索区）。"""
    bar = find_any(ctx.page, _cands(ctx, "batch_bar"), timeout=2)
    if bar is not None:
        close = find_any(ctx.page, _cands(ctx, "batch_bar_close"), timeout=2)
        if close is not None:
            try:
                close.click(timeout=6000)
                ctx.logger.info("已关闭批量操作栏")
                ctx.page.wait_for_timeout(900)
                return True
            except Exception as exc:
                ctx.logger.info("关闭批量操作栏失败：%s", exc)
    rows = _rows(ctx)
    if rows is not None:
        unchecked = 0
        for index in range(min(rows.count(), 80)):
            box = find_any(rows.nth(index), _cands(ctx, "material_checkbox"), timeout=0.3)
            if box is None:
                continue
            try:
                if box.is_checked():
                    box.uncheck()
                    unchecked += 1
            except Exception:
                continue
        if unchecked:
            ctx.logger.info("已取消 %d 条素材的勾选", unchecked)
            ctx.page.wait_for_timeout(700)
            return True
    return False


def _find_search_box(ctx: JinniuContext):
    """找素材搜索输入框（提示文字会随筛选字段变化，所以按结构定位）。"""
    target = find_any(ctx.page, _cands(ctx, "search_box"), timeout=3)
    if target is not None:
        return target
    if find_any(ctx.page, _cands(ctx, "batch_bar"), timeout=1) is not None:
        clear_selection(ctx)
        target = find_any(ctx.page, _cands(ctx, "search_box"), timeout=4)
        if target is not None:
            return target
    try:
        click_any(ctx.page, _cands(ctx, "more_filters"), timeout=6)
        ctx.page.wait_for_timeout(1200)
    except Exception as exc:
        ctx.logger.info("打不开「更多筛选」面板：%s", exc)
    return find_any(ctx.page, _cands(ctx, "search_box"), timeout=6)


def _ensure_filter_field(ctx: JinniuContext, field: str = "素材名称") -> bool:
    """把搜索区左边的筛选字段切到「素材名称」并校验。"""
    current = ""
    try:
        label = find_any(ctx.page, _cands(ctx, "filter_field_selected"), timeout=2)
        if label is not None:
            current = (label.inner_text() or "").strip()
    except Exception:
        current = ""
    if current == field:
        ctx.logger.info("筛选字段已经是「%s」，直接查询", field)
        return True
    ctx.logger.info("筛选字段当前是「%s」，正在切换到「%s」", current or "未知", field)
    last_error = None
    try:
        clicked = False
        for candidate in _cands(ctx, "filter_field_select"):
            try:
                locator = build_locator(ctx.page, candidate)
                if locator.count() == 0:
                    continue
                try:
                    locator.click(timeout=6000, force=True)
                except Exception:
                    continue
                clicked = True
                break
            except Exception as exc:
                last_error = exc
                continue
        if not clicked:
            raise RuntimeError("点不开筛选字段下拉：%s" % (last_error or "未知原因"))
        ctx.page.wait_for_timeout(800)
        option = find_any(ctx.page, _cands(ctx, "filter_field_option"), timeout=6)
        if option is None:
            ctx.logger.warning("下拉里找不到「%s」选项", field)
            return False
        option.click(timeout=8000)
        ctx.page.wait_for_timeout(800)
    except Exception as exc:
        ctx.logger.warning("切换筛选字段失败：%s", exc)
        return False
    try:
        label = find_any(ctx.page, _cands(ctx, "filter_field_selected"), timeout=3)
        after = (label.inner_text() or "").strip() if label is not None else ""
    except Exception:
        after = ""
    ok = after == field
    ctx.logger.info("筛选字段现在是「%s」%s", after or "未知", "（已切好）" if ok else "（仍不正确）")
    return ok


def _search(ctx: JinniuContext, keyword: str) -> None:
    """在素材库里按「素材名称」搜索关键词。"""
    ctx.logger.info("开始查询「%s」", keyword[:24])
    dismiss_popups(ctx)  # 查询前先清掉挡路的弹窗，否则筛选下拉点不开
    field = str(ctx.jinniu.get("filter_field") or "素材名称")
    target = _find_search_box(ctx)
    if target is None:
        raise PageChanged("找不到素材搜索框（可能需要先点开「更多筛选」面板）")
    if not _ensure_filter_field(ctx, field):
        raise PageChanged("筛选字段没能切换到「%s」，为避免查错字段，已停止" % field)
    target = _find_search_box(ctx) or target
    before = len(read_material_names(ctx, 20))
    filled = fill_quiet(ctx, _cands(ctx, "search_box"), keyword) or fill_quiet(
        ctx, _cands(ctx, "search_input"), keyword
    )
    if not filled:
        try:
            fill_any(ctx.page, _cands(ctx, "search_box"), keyword, timeout=10)
        except Exception:
            fill_any(ctx.page, _cands(ctx, "search_input"), keyword, timeout=10)
    # 诊断：确认搜索框里到底放进去的是不是完整的广告语（长文本可能被输入框长度限制截断）
    try:
        box = _find_search_box(ctx)
        actual = box.input_value() if box is not None else ""
        limit = box.get_attribute("maxlength") if box is not None else None
    except Exception:
        actual, limit = "", None
    if actual:
        if actual.strip() != keyword.strip():
            ctx.logger.warning(
                "搜索框实际内容是「%s」（%d 字），广告语是 %d 字%s —— 请把这一行发给我",
                actual[:30],
                len(actual),
                len(keyword),
                ("，输入框限制 maxlength=%s" % limit) if limit else "",
            )
        else:
            ctx.logger.info("搜索框已放入完整广告语（%d 字）", len(actual))
    ensure_page_size(ctx)
    try:
        locator = _find_search_box(ctx)
        if locator is not None:
            locator.press("Enter")
    except Exception:
        pass
    ctx.page.wait_for_timeout(1800)
    after = len(read_material_names(ctx, 20))
    if after == before:
        button = find_any(ctx.page, _cands(ctx, "search_button"), timeout=2)
        if button is not None:
            try:
                button.click(timeout=6000)
                ctx.logger.info("已点击查询按钮")
            except Exception:
                pass
    ctx.page.wait_for_timeout(1200)
    _settle(ctx)


def _clear_search(ctx: JinniuContext) -> None:
    try:
        if not (fill_quiet(ctx, _cands(ctx, "search_box"), "") or fill_quiet(ctx, _cands(ctx, "search_input"), "")):
            try:
                fill_any(ctx.page, _cands(ctx, "search_box"), "", timeout=5)
            except Exception:
                fill_any(ctx.page, _cands(ctx, "search_input"), "", timeout=5)
        button = find_any(ctx.page, _cands(ctx, "search_button"), timeout=1)
        if button is not None:
            button.click()
        ctx.page.wait_for_timeout(1200)
    except Exception:
        pass


def _rename_dialog(ctx: JinniuContext, targets: Sequence[str]) -> bool:
    """在改名弹窗里填入目标名称（多行文本框或逐行输入框）。"""
    dialog = find_any(ctx.page, _cands(ctx, "rename_dialog"), timeout=10)
    scope = dialog if dialog is not None else ctx.page
    row_inputs = find_list(scope, _cands(ctx, "rename_row_inputs"), min_count=1)
    if row_inputs is not None:
        total = min(row_inputs.count(), len(targets))
        for index in range(total):
            try:
                set_text(row_inputs.nth(index), targets[index], delay=2)
            except Exception as exc:
                ctx.logger.warning("填第 %d 行视频名称失败：%s", index + 1, exc)
        if total >= 1:
            ctx.logger.info("已在改名弹窗里逐行填入 %d 个视频名称", total)
            return True
    textarea = find_any(scope, _cands(ctx, "rename_textarea"), timeout=2)
    if textarea is not None:
        set_text(textarea, "\n".join(targets), delay=2)
        return True
    inputs = find_list(scope, _cands(ctx, "rename_name_input"), min_count=1)
    if inputs is None:
        return False
    total = min(inputs.count(), len(targets))
    for index in range(total):
        set_text(inputs.nth(index), targets[index], delay=2)
    return total >= 1


def _confirm_dialog(ctx: JinniuContext) -> bool:
    dialog = find_any(ctx.page, _cands(ctx, "rename_dialog"), timeout=3)
    scope = dialog if dialog is not None else ctx.page
    try:
        click_any(scope, _cands(ctx, "rename_confirm_button"), timeout=8)
        return True
    except Exception:
        try:
            click_any(ctx.page, _cands(ctx, "rename_confirm_button"), timeout=8)
            return True
        except Exception:
            return False


def _rename_one_row(ctx: JinniuContext, row_index: int, target: str) -> bool:
    """把列表里第 row_index 条素材改名为 target（勾选该行 → 修改视频名称 → 填一行）。"""
    rows = _rows(ctx)
    if rows is None or row_index >= rows.count():
        return False
    row = rows.nth(row_index)
    try:
        checkbox = find_any(row, _cands(ctx, "material_checkbox"), timeout=2)
        if checkbox is None:
            raise RuntimeError("这一行没有勾选框")
        if not checkbox.is_checked():
            checkbox.check()
        ctx.page.wait_for_timeout(600)
        click_any(ctx.page, _cands(ctx, "batch_rename_button"), timeout=8)
        ctx.page.wait_for_timeout(1000)
        if not _rename_dialog(ctx, [target]):
            return False
        if not _confirm_dialog(ctx):
            return False
        _settle(ctx)
        try:
            if checkbox.is_checked():
                checkbox.uncheck()
                ctx.page.wait_for_timeout(400)
        except Exception:
            pass
        return True
    except Exception as exc:
        ctx.logger.info("勾选单行改名没成功（%s），试试行内编辑入口", exc)
    try:
        click_any(row, _cands(ctx, "single_rename_button"), timeout=3)
        ctx.page.wait_for_timeout(800)
        if not _rename_dialog(ctx, [target]):
            return False
        if not _confirm_dialog(ctx):
            return False
        _settle(ctx)
        return True
    except Exception as exc:
        ctx.logger.warning("改名失败：%s", exc)
        return False


def group_by_copy(items: Sequence[Tuple[int, str, str]]) -> List[Dict[str, Any]]:
    """按广告语分组：相同广告语归为一组，组内保持文件夹顺序。"""
    order: List[str] = []
    buckets: Dict[str, List[Tuple[int, str]]] = {}
    for index, copy_text, file_name in items:
        if copy_text not in buckets:
            buckets[copy_text] = []
            order.append(copy_text)
        buckets[copy_text].append((index, file_name))
    return [{"copy": key, "items": buckets[key]} for key in order]


def targets_for_rows(names: Sequence[str], group: Dict[str, Any], list_order: str = "newest_first") -> List[str]:
    """把列表顺序换算成文件夹顺序：最新在最上面（降序）↔ 文件夹倒序。"""
    files = [file_name for _, file_name in group["items"]]
    if (list_order or "newest_first").lower() == "newest_first":
        files = list(reversed(files))
    return files[: min(len(names), len(files))]


def item_for_row(group: Dict[str, Any], position: int, list_order: str = "newest_first"):
    """列表第 position 行对应的 (序号, 文件名)。"""
    items = group["items"]
    if (list_order or "newest_first").lower() == "newest_first":
        position = len(items) - 1 - position
    return items[position] if 0 <= position < len(items) else None


def count_matches(copy_text: str, names: Sequence[str], expected: int = 1) -> int:
    """在查到的列表里数出匹配条数。"""
    if expected == 1:
        return sum(1 for name in names if copy_text[:12] in name or name[:12] in copy_text)
    return sum(1 for name in names if name.strip())


def decide_mismatch(bridge, copy_text: str, found: int, expected: int, cfg: Dict[str, Any]) -> str:
    """条数对不上时的处理决定：retry / continue / skip / stop。"""
    mode = str(((cfg or {}).get("jinniu") or {}).get("on_mismatch") or "ask").lower()
    if mode == "skip":
        return "skip"
    if mode == "retry":
        return "retry"
    # 默认（ask）也直接继续：不再弹窗询问，避免打断流程；对应关系由"视频时长"兜底校验
    return "continue"


def _wait_seconds(ctx: JinniuContext, seconds: float, reason: str) -> None:
    if seconds <= 0:
        return
    ctx.logger.info("%s（等待 %.0f 秒）", reason, seconds)
    end = time.time() + seconds
    last_logged = -1
    while time.time() < end:
        if ctx.bridge.stopped():
            raise StoppedByUser("用户停止运行")
        remain = int(end - time.time())
        if remain != last_logged:
            ctx.bridge.status("%s，还剩 %d 秒…" % (reason, remain))
            last_logged = remain
        time.sleep(1)
    ctx.bridge.status("%s完成" % reason)


def rename_by_search(ctx: JinniuContext) -> Dict[str, Any]:
    """主流程：按广告语分组查询素材 → 校验条数 → 改名为对应文件名。"""
    items: List[Tuple[int, str, str]] = []
    for index, video in enumerate(ctx.videos):
        copy_text = (ctx.copies[index] if index < len(ctx.copies) else "").strip()
        if copy_text:
            items.append((index, copy_text, video.name))
    result: Dict[str, Any] = {"mode": "按素材名称搜索", "renamed": 0, "total": len(items), "skipped": False}
    if not items:
        ctx.logger.warning(
            "这个账号还没填广告语（文件夹里有 %d 个视频），无法按素材名称查询素材库", len(ctx.videos)
        )
        result["skipped"] = True
        return result
    if len(items) < len(ctx.videos):
        ctx.logger.warning("有 %d 条视频没有对应广告语，这些不会改名", len(ctx.videos) - len(items))
    groups = group_by_copy(items)
    ctx.logger.info("共 %d 条视频，按广告语分成 %d 组查询", len(items), len(groups))
    list_order = ctx.jinniu.get("list_order")
    done = 0
    max_rounds = 5
    for order, group in enumerate(groups, start=1):
        copy_text = group["copy"]
        expected = len(group["items"])
        ctx.bridge.status(
            "金牛改名 %d/%d：查询「%s」（应有 %d 条）" % (order, len(groups), copy_text[:16], expected)
        )
        names: List[str] = []
        rounds = 0
        while True:
            if ctx.bridge.stopped():
                raise StoppedByUser("用户停止运行")
            rounds += 1
            _search(ctx, copy_text)
            full_rows = read_rows_full(ctx, limit=max(expected + 20, 60))
            names = [row[0] for row in full_rows] or read_material_names(ctx, max(expected + 3, 6))
            rows_visible = count_matches(copy_text, names, expected)
            total = read_total_count(ctx)
            found = total if total is not None else rows_visible
            ctx.logger.info(
                "查询「%s」：页面共 %s 条（可见 %d 行），应有 %d 条",
                copy_text[:20],
                total if total is not None else "未知",
                rows_visible,
                expected,
            )
            if (
                found < expected
                and len(copy_text) > 12
                and bool(ctx.jinniu.get("allow_short_keyword", False))
            ):
                # 默认关闭：截断关键词容易查到同事的素材，只有明确开启时才用
                chars = int(ctx.jinniu.get("fallback_keyword_chars", 12) or 12)
                short = build_fallback_keyword(copy_text, chars)
                ctx.logger.info(
                    "完整广告语只查到 %d 条，改用「%s」（共 %d 字）再查一次", found, short, len(short)
                )
                _search(ctx, short)
                names2 = read_material_names(ctx, max(expected + 3, 6))
                found2 = count_matches(short, names2, expected)
                ctx.logger.info("用「%s」查到 %d 条，应有 %d 条", short, found2, expected)
                if found2 > found:
                    names, found = names2, found2
            if found == expected:
                break
            decision = decide_mismatch(ctx.bridge, copy_text, found, expected, ctx.cfg)
            if rounds >= max_rounds:
                ctx.logger.warning("已经重试 %d 轮仍对不上，按跳过处理", rounds)
                decision = "skip"
            if decision == "retry":
                _wait_seconds(ctx, float(ctx.jinniu.get("retry_wait_seconds", 60) or 0), "等待素材同步后重新查询")
                continue
            if decision == "continue":
                # 按你的确认继续：不再反复查询，直接用当前查到的这些素材往下走
                ctx.logger.info(
                    "查到 %d 条素材（文件夹里共 %d 个视频），按查到条数继续改名，剩下的保持原名",
                    found,
                    expected,
                )
                break
            if decision == "skip":
                result["skipped"] = True
                ctx.logger.warning("跳过该账号的改名（查询条数与数量不一致）")
                for index, _file in group["items"]:
                    mark_state(ctx, index, rename_status="已跳过", note="查询条数与发布数量不一致")
                return result
            raise StoppedByUser("用户停止运行")
        # 对应关系以「视频时长」为准（金牛的创建时间是上传时间，和本地视频创建时间无关）
        durations = [row[3] if len(row) > 3 else None for row in full_rows]
        if len(durations) != len(names):
            durations = [None] * len(names)
        creations = [row[1] if len(row) > 1 else None for row in full_rows]
        if len(creations) != len(names):
            creations = [None] * len(names)
        resolved = match_targets_two_level(ctx, group, durations, creations)
        notes = [
            "" if target else "读不到这条素材的时长或文件夹里没有时长一致的视频"
            for target in resolved
        ]
        ordered_targets: List[str] = []
        for position, target in enumerate(resolved):
            if target:
                ordered_targets.append(target)
            else:
                if position < len(notes) and notes[position]:
                    ctx.logger.warning("第 %d 条素材：%s，保持原名不改", position + 1, notes[position])
                ordered_targets.append(names[position])
        matched = sum(1 for target in resolved if target)
        ctx.logger.info("按时长配对：%d/%d 条素材找到了对应的视频", matched, len(names))
        index_by_name = {file_name: index for index, file_name in group["items"]}
        if ordered_targets:
            ctx.logger.info(
                "改成这些名字：%s", " | ".join(item[:24] for item in ordered_targets[:3])
            )
            selected = select_all_rows(ctx)
            ctx.logger.info("已勾选 %d 条素材（当前页共 %d 条）", selected, len(names))
            targets_to_fill = ordered_targets
            if selected and selected != len(ordered_targets):
                ctx.logger.warning(
                    "勾选数量（%d）和要改的数量（%d）不一致，就按勾选到的条数改前 %d 条",
                    selected,
                    len(ordered_targets),
                    min(selected, len(ordered_targets)),
                )
                targets_to_fill = ordered_targets[:selected]
            ok = apply_batch_rename(ctx, targets_to_fill) if selected else False
            if not ok:
                ctx.logger.warning("批量改名没成功，改用逐条改名")
                for position in range(min(len(ordered_targets), len(names))):
                    if ctx.bridge.stopped():
                        raise StoppedByUser("用户停止运行")
                    if rename_material_by_name(ctx, names[position], ordered_targets[position]):
                        done += 1
            else:
                done += len(targets_to_fill)
                for target in targets_to_fill:
                    index = index_by_name.get(target)
                    if index is not None:
                        mark_state(ctx, index, rename_status="已改名")
                ctx.logger.info("本轮批量改名完成：%d 条", len(targets_to_fill))
            # 一轮改完即结束（同一关键词平台不会重新查询，重复搜索只会拿到旧结果，白跑）
            unmatched = [
                names[position]
                for position in range(len(resolved))
                if not resolved[position]
            ]
            if unmatched:
                ctx.logger.warning(
                    "本组有 %d 条没能和文件夹里的视频配上（时长读不到或没有时长一致的视频），保持原名：%s",
                    len(unmatched),
                    " | ".join(item[:20] for item in unmatched[:3]),
                )
                for position in range(len(resolved)):
                    if resolved[position]:
                        continue
                    pair = item_for_row(group, position, list_order)
                    if pair:
                        ctx.state.mark(
                            _account_name(ctx), pair[0], rename_status="待核对",
                            note="时长读不到或文件夹里没有时长一致的视频",
                        )
            ctx.logger.info("本组结束：成功改名 %d 条，未匹配 %d 条", len(targets_to_fill), len(unmatched))
            continue
        same_as_now = targets and all(
            targets[pos] == (names[pos] if pos < len(names) else "") for pos in range(len(targets))
        )
        if same_as_now:
            ctx.logger.info("这一组的素材名已经和文件名一致，不需要改名")
            for position in range(len(targets)):
                pair = item_for_row(group, position, list_order)
                if pair:
                    mark_state(ctx, pair[0], rename_status="已改名", note="原本就一致")
            done += len(targets)
            continue
        mode = str(ctx.jinniu.get("duration_check") or "auto").lower()
        need_duration = mode == "on" or (mode == "auto" and len(targets) > 1)
        if need_duration:
            ctx.logger.info("开始逐条核对素材时长（%d 条，每条约几秒）", len(targets))
            resolved, notes = resolve_by_duration(ctx, group, targets)
            adjusted: List[str] = []
            skipped_rows = 0
            for position, target in enumerate(resolved):
                note = notes[position] if position < len(notes) else ""
                if target is None:
                    current = names[position] if position < len(names) else ""
                    ctx.logger.warning("第 %d 行%s，这一条不改名", position + 1, note)
                    adjusted.append(current)
                    skipped_rows += 1
                    pair = item_for_row(group, position, list_order)
                    if pair:
                        mark_state(ctx, pair[0], rename_status="待核对", note=note)
                    continue
                if note:
                    ctx.logger.info("第 %d 行 %s", position + 1, note)
                adjusted.append(target)
            if skipped_rows:
                ctx.logger.warning("本组有 %d 条因时长不一致被跳过，请人工确认", skipped_rows)
            targets = adjusted
            if all(targets[pos] == (names[pos] if pos < len(names) else "") for pos in range(len(targets))):
                ctx.logger.info("时长校验后没有需要改名的素材，本组跳过")
                continue
        ctx.logger.info("准备改名 %d 条：%s", len(targets), " | ".join(targets[:3]) + ("…" if len(targets) > 3 else ""))
        ok = _batch_rename_by_bar(ctx, targets)
        if not ok:
            ctx.logger.warning("批量改名没成功，改用「悬浮素材名 → 点笔图标」逐条改名")
            ok = True
            for position in range(len(targets)):
                if not _rename_one_by_hover(ctx, position, targets[position]):
                    ok = False
                    break
        if not ok:
            shot = ctx.bridge.shot(ctx.page, "%s_金牛改名失败_第%d组" % (_account_name(ctx), order))
            answer = ctx.bridge.rescue(
                "金牛改名需要人工接管",
                "第 %d 组（广告语：%s）自动改名没有成功。\n可以在浏览器里手动改完，再选第一项继续。\n页面截图：%s"
                % (order, copy_text[:24], shot or "无"),
                ["我已经手动改完了，继续", "跳过这个账号的改名", "停止运行"],
            )
            if answer == "停止运行":
                raise StoppedByUser("用户停止运行")
            if answer == "跳过这个账号的改名":
                for index, _file in group["items"]:
                    mark_state(ctx, index, rename_status="已跳过", note="自动改名失败，人工选择跳过")
                result["skipped"] = True
                return result
            for position in range(len(targets)):
                pair = item_for_row(group, position, list_order)
                if pair:
                    mark_state(ctx, pair[0], rename_status="已改名", note="人工完成")
            done += len(targets)
            continue
        _search(ctx, copy_text)
        after = read_material_names(ctx, max(expected + 3, 6))
        still_there = count_matches(copy_text, after, expected)
        for position in range(len(targets)):
            pair = item_for_row(group, position, list_order)
            if not pair:
                continue
            index, file_name = pair
            mark_state(ctx,
                                index,
                rename_status="待核对" if still_there else "已改名",
                note="改名后仍能查到旧名字，请人工确认" if still_there else "",
            )
            if not still_there:
                done += 1
        ctx.logger.info(
            "第 %d 组完成：%d 条，改名后核查仍能查到 %d 条", order, len(targets), still_there
        )
    _clear_search(ctx)
    result["renamed"] = done
    return result


def _targets_in_page_order(ctx: JinniuContext) -> List[str]:
    """素材列表顺序（默认最新在上）换算成对应的视频文件名顺序。"""
    names = [video.name for video in ctx.videos]
    order = (ctx.jinniu.get("list_order") or "newest_first").lower()
    if order == "newest_first":
        return list(reversed(names))
    return names


def _select_rows(ctx: JinniuContext, count: int) -> int:
    rows = _rows(ctx)
    if rows is None:
        return 0
    selected = 0
    for index in range(min(rows.count(), count)):
        row = rows.nth(index)
        done = False
        for attempt in range(2):
            try:
                if attempt:
                    row.scroll_into_view_if_needed(timeout=4000)
                    ctx.page.wait_for_timeout(300)
                checkbox = find_any(row, _cands(ctx, "material_checkbox"), timeout=1.0)
                if checkbox is None:
                    continue
                if not checkbox.is_checked():
                    try:
                        checkbox.check(timeout=5000)
                    except Exception:
                        checkbox.check(timeout=5000, force=True)
                selected += 1
                done = True
                break
            except Exception:
                continue
        if not done:
            ctx.logger.info("第 %d 行的勾选框没能勾上，先跳过这一行", index + 1)
    return selected


def _rename_one_by_hover(ctx: JinniuContext, row_index: int, target: str) -> bool:
    """悬浮素材名称 → 点笔图标 → 改名（金牛的第二个入口）。"""
    rows = _rows(ctx)
    if rows is None or row_index >= rows.count():
        return False
    row = rows.nth(row_index)
    try:
        name_cell = find_any(row, _cands(ctx, "row_name_target"), timeout=3)
        if name_cell is not None:
            name_cell.hover()
            ctx.page.wait_for_timeout(600)
        pencil = find_any(row, _cands(ctx, "row_rename_pencil"), timeout=3)
        if pencil is None:
            pencil = find_any(ctx.page, _cands(ctx, "row_rename_pencil"), timeout=2)
        if pencil is None:
            return False
        pencil.click()
        ctx.page.wait_for_timeout(800)
        if not _rename_dialog(ctx, [target]):
            return False
        if not _confirm_dialog(ctx):
            return False
        _settle(ctx)
        return True
    except Exception as exc:
        ctx.logger.info("悬浮笔图标改名没成功：%s", exc)
        return False


def _batch_rename_by_bar(ctx: JinniuContext, targets: Sequence[str]) -> bool:
    """勾选素材 → 顶部批量栏 →「修改视频名称」→ 填名称。"""
    selected = _select_rows(ctx, len(targets))
    if not selected:
        ctx.logger.warning("没有勾选到任何素材行")
        return False
    ctx.logger.info("已勾选 %d 条素材，等待批量操作栏出现", selected)
    ctx.page.wait_for_timeout(800)
    bar = find_any(ctx.page, _cands(ctx, "batch_bar"), timeout=6)
    if bar is None:
        ctx.logger.warning("没有等到批量操作栏")
        return False
    try:
        bar_text = bar.inner_text() or ""
        numbers = re.findall(r"\d+", bar_text)
        reported = int(numbers[0]) if numbers else selected
    except Exception:
        reported = selected
    if reported <= 0:
        ctx.logger.error("一条素材都没能勾选上，停止改名以免改错")
        raise PageChanged("一条素材都没能勾选上")
    if reported != len(targets):
        # 少勾上几条没关系：勾上几条就改几条（剩下的行保持原名，时长校验会兜底）
        ctx.logger.warning(
            "勾选数量和预期不完全一致（期望 %d，实际 %d），就按勾上的 %d 条改名，其余保持原名",
            len(targets),
            reported,
            reported,
        )
        targets = list(targets[:reported])
    try:
        click_any(ctx.page, _cands(ctx, "batch_rename_button"), timeout=8)
    except Exception as exc:
        ctx.logger.warning("找不到「修改视频名称」入口：%s", exc)
        return False
    ctx.logger.info("已点击「修改视频名称」")
    ctx.page.wait_for_timeout(1200)
    if not _rename_dialog(ctx, targets):
        ctx.logger.warning("改名弹窗里没识别到输入框")
        return False
    if not _confirm_dialog(ctx):
        ctx.logger.warning("改名弹窗里没找到确定按钮")
        return False
    _settle(ctx)
    clear_selection(ctx)
    return True


def rename_by_time(ctx: JinniuContext) -> Dict[str, Any]:
    """方式二：按上传时间倒序，把当日新增素材整批改名为文件名。"""
    count = len(ctx.videos)
    targets = _targets_in_page_order(ctx)
    current = read_material_names(ctx, count)
    result = {"mode": "按上传时间倒序", "renamed": 0, "total": count}
    if not current:
        return result
    rows = [[index + 1, current[index][:40], targets[index][:40]] for index in range(min(len(current), count))]
    if ctx.jinniu.get("confirm_mapping", False):
        if not ctx.bridge.confirm_table(
            "金牛改名核对（%s）" % _account_name(ctx),
            "金牛默认把最新上传的排在列表最上面，所以列表第 1 条对应你文件夹里的最后一条视频。\n"
            "请核对下面「素材当前名 → 要改成的新名字」。",
            ["列表第几条", "素材当前名", "要改成的新素材名"],
            rows,
        ):
            raise StoppedByUser("用户取消改名")
    if current[:count] == targets[:count]:
        ctx.logger.info("素材名已经和文件名一致，无需修改")
        for index in range(count):
            mark_state(ctx, index, rename_status="已改名", note="原本就一致")
        result["renamed"] = count
        return result
    ok = _batch_rename_by_bar(ctx, targets)
    if not ok:
        ctx.logger.warning("批量改名没成功，改用「悬浮素材名 → 点笔图标」逐条改名")
        total = min(len(current), count)
        done = 0
        for index in range(total):
            if _rename_one_by_hover(ctx, index, targets[index]):
                done += 1
        ok = done == total
    if not ok:
        ctx.logger.warning("再试一次逐条改名（行内编辑入口）")
        ok = all(_rename_one_row(ctx, index, targets[index]) for index in range(min(len(current), count)))
    if not ok:
        return result
    ctx.page.wait_for_timeout(1500)
    after = read_material_names(ctx, count)
    matched = sum(1 for index in range(min(len(after), count)) if after[index].strip() == targets[index].strip())
    ctx.logger.info("改名后核对：%d/%d 条与文件名一致", matched, count)
    reverse = (ctx.jinniu.get("list_order") or "newest_first") == "newest_first"
    for index in range(count):
        page_position = count - 1 - index if reverse else index
        ok_flag = page_position < len(after) and after[page_position].strip() == targets[page_position].strip()
        mark_state(ctx,
                        index,
            rename_status="已改名" if ok_flag else "待核对",
            note="" if ok_flag else "改名后未核对到一致，请人工确认",
        )
    result["renamed"] = matched
    return result


def _manual_rescue(ctx: JinniuContext, reason: str) -> Dict[str, Any]:
    shot = ctx.bridge.shot(ctx.page, "%s_金牛改名异常" % _account_name(ctx))
    answer = ctx.bridge.rescue(
        "金牛改名需要人工接管",
        "自动改名没有成功（%s）。请在打开的浏览器里手动完成改名，或选择跳过。\n页面截图：%s" % (reason, shot or "无"),
        ["我已经手动改完了，继续", "跳过这个账号", "停止运行"],
    )
    count = len(ctx.videos)
    if answer == "我已经手动改完了，继续":
        for index in range(count):
            mark_state(ctx, index, rename_status="已改名", note="人工完成")
        return {"mode": "人工", "renamed": count, "total": count}
    if answer == "跳过这个账号":
        for index in range(count):
            mark_state(ctx, index, rename_status="已跳过", note="自动改名失败")
        return {"mode": "已跳过", "renamed": 0, "total": count}
    raise StoppedByUser("用户停止运行")


def run_account(ctx: JinniuContext, after_publish: bool = False) -> Dict[str, Any]:
    """跑完一个账号的素材改名。after_publish=True 表示刚刚在同一轮里发布过素材。"""
    try:
        first_names = [video.name for video in ctx.videos[:3]]
        if first_names:
            ctx.logger.info("这个文件夹里的文件名（前 3 个）：%s", " | ".join(first_names))
        ctx.logger.info("这个文件夹里共有 %d 个视频", len(ctx.videos))
    except Exception:
        pass
    wait_seconds = float(ctx.jinniu.get("sync_wait_seconds", 60) or 0)
    if wait_seconds > 0:
        if after_publish:
            _wait_seconds(ctx, wait_seconds, "等待素材同步到金牛素材库")
        else:
            # 单独改名时不再弹窗询问（弹窗容易让人以为程序卡住），直接开始改；
            # 素材没同步好的话，搜索自然查不到，日志里会写清楚。
            ctx.logger.info("单独执行改名：不等待同步，直接开始（若查不到素材，说明还没同步到金牛）")
    ensure_library_page(ctx)
    mode = (ctx.jinniu.get("rename_mode") or "auto").lower()
    filled = [item for item in ctx.copies if item.strip()]
    has_copies = len(filled) >= 1
    if not has_copies and mode in ("by_title", "auto"):
        # 不再弹窗：没广告语时直接停止这个账号的改名（避免误改同事的素材）
        ctx.logger.warning(
            "这个账号还没有填写广告语，已跳过它的改名。请先回主界面粘贴广告语（广告语必须唯一），再重新执行。"
        )
        for index in range(len(ctx.videos)):
            mark_state(ctx, index, rename_status="已跳过", note="未填写广告语")
        result["skipped"] = True
        return result
        mode = "by_time_reverse"
    if mode in ("by_title", "auto") and has_copies:
        try:
            result = rename_by_search(ctx)
            if result.get("renamed") or result.get("skipped") or not result.get("total"):
                shot = ctx.bridge.shot(ctx.page, "%s_金牛改名完成" % _account_name(ctx))
                ctx.logger.info("按素材名称查询改名结束：%s（截图：%s）", result, shot or "无")
                return result
            ctx.logger.warning("按素材名称查询没有改到任何素材，改用按时间倒序方式")
        except StoppedByUser:
            raise
        except Exception as exc:
            ctx.logger.warning("按素材名称查询改名失败：%s", exc)
            # 查询/筛选失败时绝不自动改用按时间对应改名，避免改错素材
            return _manual_rescue(ctx, "按素材名称查询失败：%s" % exc)
    if mode in ("by_time_reverse", "auto", "by_title"):
        try:
            result = rename_by_time(ctx)
        except StoppedByUser:
            raise
        except Exception as exc:
            ctx.logger.warning("按时间倒序改名失败：%s", exc)
            return _manual_rescue(ctx, str(exc))
        if result.get("renamed") or result.get("total"):
            shot = ctx.bridge.shot(ctx.page, "%s_金牛改名完成" % _account_name(ctx))
            ctx.logger.info("按时间倒序改名结束：%s（截图：%s）", result, shot or "无")
            return result
        return _manual_rescue(ctx, "没有识别到可改名的素材")
    return _manual_rescue(ctx, "未知的改名方式：%s" % mode)
