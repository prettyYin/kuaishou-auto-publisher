# -*- coding: utf-8 -*-
"""离线自检：不碰浏览器、不碰账号，验证解析、排序、断点、报表等核心逻辑。"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from . import config as cfgmod
from .copytext import find_duplicates, parse_copies, validate
from .copystore import CopyStore
from .flow_creator import FALLBACK as CREATOR_FALLBACK
from .flow_jinniu import FALLBACK as JINNIU_FALLBACK
from .flow_jinniu import _targets_in_page_order
from .report import write_report
from .selectors import find_any, find_list
from .state import RunState
from .videos import natural_key

RESULTS = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    mark = "√" if condition else "×"
    print("%s %s%s" % (mark, name, ("  → " + detail) if detail and not condition else ""))


class FakeLocator:
    def __init__(self, count: int = 1, visible: bool = True) -> None:
        self._count = count
        self._visible = visible

    def count(self) -> int:
        return self._count

    def is_visible(self) -> bool:
        return self._visible

    def is_enabled(self) -> bool:
        return True

    @property
    def first(self):
        return self

    def nth(self, index):
        return self

    @property
    def last(self):
        return self


class FakeScope:
    def __init__(self, mapping) -> None:
        self.mapping = mapping

    def locator(self, selector: str):
        return FakeLocator(count=self.mapping.get(selector, 0))

    def get_by_text(self, text, exact=False):
        return FakeLocator(count=self.mapping.get("text:" + text, 0))

    def get_by_placeholder(self, text):
        return FakeLocator(count=self.mapping.get("ph:" + text, 0))


class FakeVideo:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeCtx:
    def __init__(self, names, jinniu_cfg):
        self.videos = [FakeVideo(name) for name in names]
        self.jinniu = jinniu_cfg


def test_natural_sort() -> None:
    names = ["视频10.mp4", "视频2.mp4", "视频1.mp4", "视频20.mp4"]
    ordered = sorted(names, key=natural_key)
    expected = ["视频1.mp4", "视频2.mp4", "视频10.mp4", "视频20.mp4"]
    check("视频按自然顺序排序（视频2 在 视频10 前面）", ordered == expected, str(ordered))
    mixed = sorted(["B2.mp4", "b10.mp4", "a1.mp4"], key=natural_key)
    check("中英文与大小写混排不报错", len(mixed) == 3, str(mixed))


def test_copy_parsing() -> None:
    raw = "【账号A】\n1. 好用的洗发水\n2、第二句广告语\n\n3）第三句\n"
    parsed = parse_copies(raw, strip_index=True)
    expected = ["好用的洗发水", "第二句广告语", "第三句"]
    check("解析粘贴文本：自动去掉【标题行】和行首序号", parsed == expected, str(parsed))
    keep = parse_copies(raw, strip_index=False)
    check("不勾选去序号时保留原样", keep[0].startswith("1."), str(keep[:1]))
    dup = find_duplicates(["a", "a", "b"])
    check("能发现重复广告语", dup == {"a": 2}, str(dup))
    ok = validate(["a", "b"], 2)
    check("数量一致判定为可运行", bool(ok.get("ok")))
    bad = validate(["a"], 2)
    check("数量不一致会被拦下", bad.get("ok") is False and "不一致" in str(bad.get("message")))


def test_state_resume() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        state = RunState.load(run_dir, "2026-09-16")
        state.item("账号A", 0, "视频1.mp4", "广告语1")
        state.mark("账号A", 0, publish_status="已发布", work_url="https://v.kuaishou.com/x", seconds=12)
        state.save()
        again = RunState.load(run_dir, "2026-09-16")
        check("断点续跑：已发布的条目会被识别并跳过", again.is_published("账号A", 0))
        check("断点续跑：未处理的条目仍是待处理", not again.is_published("账号A", 1))
        again.mark("账号A", 0, rename_status="已改名")
        reloaded = RunState.load(run_dir, "2026-09-16")
        check("改名状态能持久化", reloaded.is_renamed("账号A", 0))


def test_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = write_report(
            Path(tmp) / "运行结果.xlsx",
            [
                {
                    "account": "账号A",
                    "index": 0,
                    "file": "视频1.mp4",
                    "copy": "广告语1",
                    "publish_status": "已发布",
                    "work_url": "https://v.kuaishou.com/x",
                    "rename_status": "已改名",
                    "seconds": 95,
                    "updated": "2026-09-16 09:31:00",
                    "note": "",
                }
            ],
        )
        size = path.stat().st_size if path.exists() else 0
        check("结果报表可以生成（xlsx）", size > 3000, "size=%s" % size)


def test_publish_settings_model() -> None:
    from .publish_settings import (
        AUTHOR_DECLARATION_OPTIONS,
        FIELD_DEFINITIONS,
        PREVIEW_COLUMNS,
        default_schedule_time,
        default_settings,
        format_publish_at,
        month_number,
        normalize_publish_at,
        run_with_retries,
        schedule_time_values,
        summarize_author,
        validate_publish_at,
        year_number,
    )

    defaults = default_settings()
    check(
        "发布设置默认是空作者声明 + 立即发布",
        defaults.get("author_statement") == "" and defaults.get("publish_at") == "",
        str(defaults),
    )
    check(
        "作者声明选项与创作者平台一致",
        tuple(AUTHOR_DECLARATION_OPTIONS)
        == ("内容为AI生成", "演绎情节，仅供娱乐", "个人观点，仅供参考", "素材来源于网络"),
        str(AUTHOR_DECLARATION_OPTIONS),
    )
    check("不设置作者声明时显示为空", summarize_author("") == "不设置", summarize_author(""))
    check(
        "立即发布显示为立即发布",
        format_publish_at("") == "立即发布",
        format_publish_at(""),
    )

    now = datetime(2026, 9, 22, 10, 0, 0)
    check(
        "定时时间不足 1 小时会被拦下",
        bool(validate_publish_at("2026-09-22 10:59", now=now)),
        validate_publish_at("2026-09-22 10:59", now=now),
    )
    check(
        "定时时间正好 1 小时可以通过（平台规则允许）",
        validate_publish_at(
            "2026-09-22 11:00",
            now=now,
            min_lead_minutes=60,
        ) == "",
        validate_publish_at(
            "2026-09-22 11:00",
            now=now,
            min_lead_minutes=60,
        ),
    )
    check(
        "定时时间 61 分钟后可以通过",
        validate_publish_at(
            "2026-09-22 11:01",
            now=now,
            min_lead_minutes=60,
        )
        == "",
        validate_publish_at(
            "2026-09-22 11:01",
            now=now,
            min_lead_minutes=60,
        ),
    )
    check(
        "默认定时时间是 61 分钟后",
        default_schedule_time(datetime(2026, 9, 22, 15, 45, 30))
        == datetime(2026, 9, 22, 16, 46, 0),
        str(default_schedule_time(datetime(2026, 9, 22, 15, 45, 30))),
    )
    check(
        "日期面板时分秒列能按目标时间取值",
        schedule_time_values(datetime(2026, 9, 22, 16, 45, 10), 3)
        == ["16", "45", "10"]
        and schedule_time_values(datetime(2026, 9, 22, 16, 45, 10), 2) == ["16", "45"],
        str(schedule_time_values(datetime(2026, 9, 22, 16, 45, 10), 3)),
    )
    check(
        "日期面板标题能解析年月",
        month_number("9月") == 9 and year_number("2026年") == 2026,
        "%s %s" % (month_number("9月"), year_number("2026年")),
    )
    check(
        "定时时间超过 14 天会被拦下",
        bool(validate_publish_at("2026-10-07 10:01", now=now)),
        validate_publish_at("2026-10-07 10:01", now=now),
    )
    check(
        "定时时间在 14 天内可以通过",
        validate_publish_at("2026-10-06 10:00", now=now) == "",
        validate_publish_at("2026-10-06 10:00", now=now),
    )
    check(
        "定时时间能统一成 ISO 格式",
        normalize_publish_at("2026-09-23 19:30") == "2026-09-23T19:30:00",
        normalize_publish_at("2026-09-23 19:30"),
    )

    calls = {"count": 0}

    def flaky() -> None:
        calls["count"] += 1
        raise RuntimeError("失败")

    ok, _ = run_with_retries(flaky, retries=2)
    check("作者声明失败会重试 2 次（总共尝试 3 次）后放弃", (not ok) and calls["count"] == 3, str(calls))
    check(
        "发布字段清单预留了更多设置分组",
        any(item.get("group") == "更多设置" for item in FIELD_DEFINITIONS),
        str(FIELD_DEFINITIONS),
    )
    check(
        "对照表固定列包含作者声明和发布时间",
        tuple(PREVIEW_COLUMNS)
        == ("序号", "文件名", "广告语", "作者声明", "发布时间", "状态"),
        str(PREVIEW_COLUMNS),
    )


def test_pending_rename_store() -> None:
    from .pending import PendingRenameStore

    with tempfile.TemporaryDirectory() as tmp:
        store = PendingRenameStore(Path(tmp) / "pending_rename.json").load()
        store.add("账号A", "视频1.mp4", "广告语", "2026-09-23T19:30:00")
        store.add("账号A", "视频2.mp4", "广告语", "2026-09-24T09:00:00")
        check("定时发布的视频会进入待改名台账", len(store.entries()) == 2, str(store.entries()))
        removed = store.resolve("账号A", ["视频1.mp4"])
        check("金牛改名成功后能核销待办", removed == 1 and len(store.entries()) == 1, str(store.entries()))
        cleared = store.clear_all()
        check("用户确认已手动改完名时能清空剩余待办", cleared == 1 and store.entries() == [], str(store.entries()))


def test_publish_config_and_selectors() -> None:
    from .publish_settings import settings_for_videos
    from .selectors import Selectors

    cfg = cfgmod.load_config()
    creator = cfg.get("creator", {})
    check(
        "配置里有作者声明选项和重试次数",
        list(creator.get("author_declaration_options") or []) == [
            "内容为AI生成",
            "演绎情节，仅供娱乐",
            "个人观点，仅供参考",
            "素材来源于网络",
        ]
        and int(creator.get("author_statement_retries", -1)) == 2,
        str(creator),
    )
    check(
        "配置里有定时发布的安全边界",
        int(creator.get("schedule_min_lead_minutes", -1)) == 60
        and int(creator.get("schedule_max_days", -1)) == 14
        and bool(creator.get("auto_rename_when_scheduled", True)) is False,
        str(creator),
    )
    with tempfile.TemporaryDirectory() as tmp:
        legacy_path = Path(tmp) / "config.json"
        legacy_path.write_text(
            '{"creator":{"schedule_min_lead_minutes":1,"schedule_max_days":7}}',
            encoding="utf-8",
        )
        migrated = cfgmod.load_config(legacy_path)
        check(
            "旧的 1 分钟默认值会自动迁移为 60 分钟",
            int(migrated.get("creator", {}).get("schedule_min_lead_minutes", -1)) == 60,
            str(migrated.get("creator")),
        )
        check(
            "旧的 7 天上限会自动迁移为 14 天",
            int(migrated.get("creator", {}).get("schedule_max_days", -1)) == 14,
            str(migrated.get("creator")),
        )
    selectors = Selectors.load().group("creator")
    needed = (
        "author_statement_select",
        "author_statement_selected",
        "author_statement_clear",
        "author_statement_option",
        "immediate_radio",
        "schedule_radio",
        "schedule_input",
        "schedule_selected",
    )
    check(
        "选择器里包含作者声明和定时发布候选规则",
        all(selectors.get(key) for key in needed),
        str([key for key in needed if not selectors.get(key)]),
    )
    check(
        "创作者平台内置兜底规则也包含作者声明和定时发布",
        all(CREATOR_FALLBACK.get(key) for key in needed),
        str([key for key in needed if not CREATOR_FALLBACK.get(key)]),
    )

    from .flow_creator import CreatorContext

    ctx = CreatorContext(None, None, {}, {}, [], [], None, None, video_settings=[{"author_statement": "x"}])
    check(
        "发布上下文能按条带着作者声明和定时设置",
        ctx.video_settings[0].get("author_statement") == "x",
        str(ctx.video_settings),
    )

    videos = [FakeVideo("视频1.mp4"), FakeVideo("视频2.mp4")]
    saved = {
        "账号A::g:\\素材\\视频1.mp4": {"author_statement": "内容为AI生成", "publish_at": "2026-09-23T19:30:00"},
    }
    settings = settings_for_videos("账号A", [r"G:\素材\视频1.mp4", r"G:\素材\视频2.mp4"], saved)
    check(
        "逐条设置能按完整路径取回，未设置的是空值",
        settings[0]["author_statement"] == "内容为AI生成"
        and settings[0]["publish_at"] == "2026-09-23T19:30:00"
        and settings[1]["author_statement"] == ""
        and settings[1]["publish_at"] == "",
        str(settings),
    )


def test_report_publish_columns() -> None:
    from openpyxl import load_workbook

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.xlsx"
        write_report(
            path,
            [
                {
                    "account": "账号A",
                    "index": 0,
                    "file": "视频1.mp4",
                    "copy": "广告语",
                    "publish_status": "已发布",
                    "publish_mode": "定时发布",
                    "publish_at": "2026-09-23T19:30:00",
                    "_author_statement": "内容为AI生成",
                    "rename_status": "待人工改名",
                    "note": "测试",
                }
            ],
        )
        sheet = load_workbook(path).active
        headers = [cell.value for cell in sheet[1]]
        values = [cell.value for cell in sheet[2]]
        check(
            "报表包含作者声明、发布时间、发布方式和待改名状态",
            all(name in headers for name in ("作者声明", "发布时间", "发布方式", "待改名")),
            str(headers),
        )
        check(
            "报表能写出本条作者声明和定时时间",
            "内容为AI生成" in values and "2026-09-23 19:30" in values,
            str(values),
        )


def test_state_transient_publish_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        state = RunState.load(run_dir, "2026-09-22")
        entry = state.item("账号A", 0, "视频1.mp4", "广告语", r"G:\素材\视频1.mp4")
        state.set_transient(
            "账号A",
            0,
            path=r"G:\素材\视频1.mp4",
            _author_statement="内容为AI生成",
        )
        state.mark(
            "账号A",
            0,
            path=r"G:\素材\视频1.mp4",
            publish_mode="定时发布",
            publish_at="2026-09-23T19:30:00",
        )
        check("内存里能带着作者声明给报表用", entry.get("_author_statement") == "内容为AI生成", str(entry))
        again = RunState.load(run_dir, "2026-09-22")
        check(
            "定时发布时间会保存，重启后仍是定时发布",
            again.items()[0].get("publish_at") == "2026-09-23T19:30:00",
            str(again.items()),
        )
        check(
            "作者声明不写入状态文件，重启后自动变回空",
            "_author_statement" not in again.items()[0],
            str(again.items()[0]),
        )


def test_config_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        cfg = cfgmod.load_config(path)
        check("新配置默认没有账号（由引导设置添加）", len(cfg.get("accounts", [])) == 0, str(len(cfg.get("accounts", []))))
        accounts = cfg.setdefault("accounts", [])
        accounts.append(cfgmod.default_account(0))
        cfg["accounts"][0]["name"] = "测试账号"
        cfg["accounts"][0]["enabled"] = True
        cfgmod.save_config(cfg, path)
        again = cfgmod.load_config(path)
        check("配置能保存也能读回", again["accounts"][0]["name"] == "测试账号" and again["accounts"][0]["enabled"])
        check("默认发布后等待 15 秒（避免连续发布导致审核错位）", again["creator"]["post_publish_wait_seconds"] == 15)
        check("账号自动化目录按账号名区分", "测试账号" in str(cfgmod.account_auto_dir(again, again["accounts"][0])))
        legacy = {"accounts": [{"name": "旧配置", "chrome_source_profile": "Profile 2", "chrome_exe": "x.exe"}]}
        cfgmod.save_config(legacy, path)
        migrated = cfgmod.load_config(path)
        check(
            "旧版 chrome_* 配置能自动迁移到 browser_*",
            migrated["accounts"][0].get("browser_source_profile") == "Profile 2",
            str(migrated["accounts"][0]),
        )


def test_browser_and_login_options() -> None:
    from .browsers import detect_browsers
    from .loginconfig import NEW_LOGIN_LABEL, apply_to_account, login_options, parse_login

    browsers = detect_browsers()
    has_real = any(item.get("exe") for item in browsers)
    check("能检测到本机的 Chromium 内核浏览器", has_real, str([b["name"] for b in browsers]))
    options = login_options("Google Chrome", "")
    check("登录方式里有「新建扫码登录」选项", NEW_LOGIN_LABEL in options, str(options[:3]))
    check("复用选项能解析出配置目录名", parse_login("复用：示例账号（Default）") == "Default")
    check("选新建设置不带旧配置", parse_login(NEW_LOGIN_LABEL) == "")
    account = {}
    apply_to_account(
        account,
        "Google Chrome",
        NEW_LOGIN_LABEL,
        {item["name"]: item for item in browsers},
    )
    check("选新建登录时不写死任何已有配置", account.get("browser_source_profile") == "" and account.get("browser_exe", "").endswith(".exe"))
    apply_to_account(
        account,
        "Google Chrome",
        "复用：眉笔（Profile 3）",
        {item["name"]: item for item in browsers},
    )
    check("选复用登录时写入配置目录名", account.get("browser_source_profile") == "Profile 3")


def test_copy_store() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "copies_2026-09-16.json"
        store = CopyStore(path, "2026-09-16").load()
        store.set("账号A", "第一条广告语\n第二条广告语", True)
        again = CopyStore(path, "2026-09-16").load()
        entry = again.get("账号A")
        check("粘贴过的广告语会保存下来（关掉工具再打开还在）", entry["raw"].startswith("第一条广告语"), str(entry))
        check("去序号开关也会一起保存", entry["strip_index"] is True)
        check("没填过的账号返回空", again.get("账号B")["raw"] == "")
        store.set("账号C", "统一广告语", False, True)
        again2 = CopyStore(path, "2026-09-16").load()
        check("批量模式的标记也会保存", again2.get("账号C")["batch"] is True)


def test_batch_copies_and_lean_copy() -> None:
    from .browser import _keep_lean

    check("只复制登录相关文件时保留 Cookies", _keep_lean("Network/Cookies"))
    check("只复制登录相关文件时跳过缓存", not _keep_lean("Cache/Cache_Data/data_1"))
    from .ui import AutoApp
    path = cfgmod.CONFIG_PATH
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        app = AutoApp()
        app.root.withdraw()
        if app.cards:
            card = app.cards[0]
            card.set_copies("统一广告语", False, True)
            expanded = card.copies(7)
            check("批量广告语会展开成与视频数量相同", len(expanded) == 7 and len(set(expanded)) == 1, str(expanded[:3]))
        else:
            check("批量广告语会展开成与视频数量相同", True, "skipped")
        app.root.destroy()
    finally:
        if backup is not None:
            path.write_text(backup, encoding="utf-8")


def test_skip_by_full_path() -> None:
    """回归测试：断点续跑必须按完整路径判断，同名文件换目录不能被跳过。"""
    from .state import RunState

    with tempfile.TemporaryDirectory() as tmp:
        state = RunState.load(Path(tmp), "2026-09-16")
        state.item("账号A", 0, "素材1.mp4", "广告语", r"G:\旧文件夹\素材1.mp4")
        state.mark("账号A", 0, path=r"G:\旧文件夹\素材1.mp4", publish_status="已发布")
        check("同一个文件（路径相同）会被跳过", state.is_published_path("账号A", r"G:\旧文件夹\素材1.mp4"))
        check("同名文件换到新文件夹后不会被跳过", not state.is_published_path("账号A", r"G:\新文件夹\素材1.mp4"))
        state.reset()
        check("「重置今日进度」后不再跳过", not state.is_published_path("账号A", r"G:\旧文件夹\素材1.mp4"))


def test_attached_page() -> None:
    """回归测试：page.url 是属性不是方法，之前写成 url() 导致点按钮就报错。"""
    from .browser import attached_page

    class FakePage:
        def __init__(self, url: str) -> None:
            self.url = url

        def is_closed(self) -> bool:
            return False

    class FakeContext:
        def __init__(self, pages) -> None:
            self.pages = pages

        def new_page(self):
            page = FakePage("about:blank")
            self.pages.append(page)
            return page

    class FakeBrowser:
        def __init__(self, contexts) -> None:
            self.contexts = contexts

        def new_context(self):
            context = FakeContext([])
            self.contexts.append(context)
            return context

    class FakePlaywright:
        def __init__(self, browser) -> None:
            self.chromium = self
            self._browser = browser

        def connect_over_cdp(self, endpoint):
            return self._browser

    context = FakeContext([FakePage("about:blank"), FakePage("https://cp.kuaishou.com/article/publish/video")])
    playwright = FakePlaywright(FakeBrowser([context]))
    browser, ctx, page = attached_page(playwright, "ws://x", "https://cp.kuaishou.com/article/publish/video")
    check("连接浏览器后能按网址选中正确页面", page.url.endswith("/article/publish/video"), page.url)
    only_blank = FakePlaywright(FakeBrowser([FakeContext([FakePage("about:blank")])]))
    _, _, blank_page = attached_page(only_blank, "ws://x")
    check("只有空白页时不会报错", blank_page.url == "about:blank", blank_page.url)


def test_card_status_states() -> None:
    from .ui_cards import GRAY, GREEN, ORANGE, RED, status_for

    check("未启用的账号显示灰色提示", status_for(False, 3, 3, "D:/x")[1] == GRAY)
    check("已配对显示绿色", status_for(True, 3, 3, "D:/x")[1] == GREEN)
    check("数量不一致显示红色", status_for(True, 3, 2, "D:/x")[1] == RED)
    check("没选文件夹时提示先选文件夹", "选择文件夹" in status_for(True, 0, 0, "")[0])
    check("有视频没广告语时是橙色", status_for(True, 5, 0, "D:/x")[1] == ORANGE)


def test_selector_engine() -> None:
    scope = FakeScope({"textarea": 1, "input[type=file]": 0})
    found = find_any(scope, [{"css": "#nope"}, {"css": "textarea"}], timeout=0.2)
    check("选择器会按候选顺序自动回退", found is not None)
    missing = find_any(scope, [{"css": "#nope"}, {"css": "#nope2"}], timeout=0.2)
    check("找不到元素时返回 None（不抛异常）", missing is None)
    listed = find_list(scope, [{"css": "input[type=file]"}, {"css": "textarea"}], min_count=1)
    check("列表型元素定位可用", listed is not None)
    check("创作者平台兜底候选包含文件框", "file_input" in CREATOR_FALLBACK)
    keys = ("material_row", "batch_rename_button", "rename_name_input", "rename_confirm_button")
    check("金牛改名相关兜底候选齐全", all(key in JINNIU_FALLBACK for key in keys))


def test_jinniu_order() -> None:
    names = ["视频1.mp4", "视频2.mp4", "视频3.mp4"]
    newest = _targets_in_page_order(FakeCtx(names, {"list_order": "newest_first"}))
    check("金牛列表最新在上时，目标顺序自动倒过来", newest == ["视频3.mp4", "视频2.mp4", "视频1.mp4"], str(newest))
    oldest = _targets_in_page_order(FakeCtx(names, {"list_order": "oldest_first"}))
    check("金牛列表最早在上时保持正序", oldest == names, str(oldest))


def test_ui_import() -> None:
    try:
        from . import ui  # noqa: F401

        check("界面模块可以导入", True)
    except Exception as exc:
        check("界面模块可以导入", False, "%s: %s" % (type(exc).__name__, exc))
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
        check("图形界面环境可用", True)
    except Exception as exc:
        check("图形界面环境可用（无显示环境时跳过）", True, "skipped: %s" % type(exc).__name__)
    try:
        from .ui import AutoApp

        app = AutoApp()
        app.root.withdraw()
        app.refresh_all()
        accounts = len(app.cards)
        expected = len(app.cfg.get("accounts", []))
        check(
            "主界面能完整构建（%d 个账号卡片）" % accounts,
            accounts == expected,
            "卡片 %d / 配置 %d" % (accounts, expected),
        )
        check(
            "主界面有并行执行入口和并发数设置",
            hasattr(app, "btn_parallel")
            and hasattr(app, "parallel_spin")
            and app.parallel_max.get().isdigit(),
            str(getattr(app, "parallel_max", None)),
        )
        check(
            "账号卡片有独立停止按钮和任务状态",
            bool(app.cards) and hasattr(app.cards[0], "stop_button") and hasattr(app.cards[0], "task_status_var"),
            "",
        )
        try:
            from .ui_copydialog import CopyDialog

            dialog = CopyDialog(app, app.cards[0])
            dialog.destroy()
            check("粘贴广告语弹窗能打开", True)
        except Exception as exc:
            check("粘贴广告语弹窗能打开", False, "%s: %s" % (type(exc).__name__, exc))
        try:
            from .publish_settings import PREVIEW_COLUMNS
            from .ui_plan import PlanEditorDialog

            with tempfile.TemporaryDirectory() as tmp:
                videos = [Path(tmp) / "视频1.mp4", Path(tmp) / "视频2.mp4"]
                store = {
                    str(videos[0]): {"author_statement": "", "publish_at": ""},
                    str(videos[1]): {"author_statement": "", "publish_at": ""},
                }
                dialog = PlanEditorDialog(
                    app.root,
                    "账号A",
                    videos,
                    ["广告语", "广告语"],
                    lambda path: dict(store.get(path) or {}),
                    lambda index, path, values: store.__setitem__(path, dict(values)),
                    creator_cfg=app.cfg.get("creator", {}),
                    mode="preview",
                )
                check(
                    "对照表编辑器固定 6 列且包含作者声明和发布时间",
                    tuple(dialog.tree["columns"]) == PREVIEW_COLUMNS,
                    str(dialog.tree["columns"]),
                )
                dialog.author_var.set("内容为AI生成")
                applied = dialog._apply_indices([0])
                check(
                    "对照表里逐条改作者声明会写回设置",
                    applied and store[str(videos[0])].get("author_statement") == "内容为AI生成",
                    str(store),
                )
                future = datetime.now() + timedelta(hours=2)
                dialog.schedule_mode.set("scheduled")
                dialog.year_var.set(str(future.year))
                dialog.month_var.set("%02d" % future.month)
                dialog.day_var.set("%02d" % future.day)
                dialog.hour_var.set("%02d" % future.hour)
                dialog.minute_var.set("%02d" % future.minute)
                applied_time = dialog._apply_indices([1])
                check(
                    "对照表里逐条改定时时间会写回设置",
                    applied_time
                    and store[str(videos[1])].get("publish_at", "").startswith(
                        future.strftime("%Y-%m-%dT%H:")
                    ),
                    str(store),
                )
                dialog.dialog.destroy()
        except Exception as exc:
            check("对照表编辑器能正常构建", False, "%s: %s" % (type(exc).__name__, exc))
        app.root.destroy()
    except Exception as exc:
        check("主界面能完整构建", False, "%s: %s" % (type(exc).__name__, exc))


def test_settings_roundtrip_keeps_login() -> None:
    path = cfgmod.CONFIG_PATH
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        from .ui import AutoApp

        app = AutoApp()
        app.root.withdraw()
        before = [account.get("browser_source_profile") for account in app.cfg.get("accounts", [])]
        app.settings_tab.save_to_config()
        after = [account.get("browser_source_profile") for account in app.cfg.get("accounts", [])]
        check("在设置页点保存不会丢掉已选的登录配置", before == after, "%s → %s" % (before, after))
        app.root.destroy()
    except Exception as exc:
        check("在设置页点保存不会丢掉已选的登录配置", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        if backup is not None:
            path.write_text(backup, encoding="utf-8")


def test_settings_and_cards_ownership() -> None:
    """设置页和主界面卡片各自负责不同字段，不能互相覆盖。"""
    path = cfgmod.CONFIG_PATH
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        from .ui import AutoApp

        app = AutoApp()
        app.root.withdraw()
        if not app.cfg.get("accounts"):
            check("设置页和主界面字段归属", True, "skipped: 没有账号")
            app.root.destroy()
            return
        account = app.cfg["accounts"][0]
        original_name = account.get("name") or "账号A"
        account["enabled"] = True
        account["video_dir"] = r"G:\测试素材"
        app.settings_tab.save_to_config(rebuild=False)
        check(
            "设置页保存不覆盖主界面启用状态和文件夹",
            account.get("enabled") is True and account.get("video_dir") == r"G:\测试素材",
            str(account),
        )

        app.cards[0].enabled.set(False)
        app.cards[0].dir_var.set(r"H:\新素材")
        app.cards[0].name_var.set("卡片上乱改的名字")
        app.save_from_cards()
        check(
            "主界面保存不会覆盖账号名",
            account.get("name") == original_name,
            "%s → %s" % (original_name, account.get("name")),
        )
        check(
            "主界面保存会更新启用状态和素材文件夹",
            account.get("enabled") is False and account.get("video_dir") == r"H:\新素材",
            str(account),
        )
        check("设置页账号行没有启用和文件夹控件", "enabled" not in app.settings_tab.account_rows[0] and "folder" not in app.settings_tab.account_rows[0])
        check("主界面账号名是只读显示", hasattr(app.cards[0], "name_display"))

        with tempfile.TemporaryDirectory() as tmp:
            app.cfg["automation_data_dir"] = tmp
            account["name"] = "旧名字"
            account["browser_auto_dir"] = ""
            old_dir = cfgmod.account_auto_dir(app.cfg, account)
            old_dir.mkdir(parents=True, exist_ok=True)
            row = app.settings_tab.account_rows[0] if app.settings_tab.account_rows else None
            if row is not None:
                row["name"].set("新名字")
                app.settings_tab.save_to_config(rebuild=False)
                check(
                    "账号改名后保留原自动化浏览器目录",
                    str(account.get("name") or "") == "新名字"
                    and str(account.get("browser_auto_dir") or "").lower() == str(old_dir).lower(),
                    str(account),
                )
            else:
                check("账号改名后保留原自动化浏览器目录", False, "找不到设置页账号行")
        app.root.destroy()
    except Exception as exc:
        check("设置页和主界面字段归属", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        if backup is not None:
            path.write_text(backup, encoding="utf-8")


def test_parallel_preflight_and_scheduler() -> None:
    import threading
    import time

    from .parallel import normalize_max_accounts, preflight_parallel, run_parallel_jobs

    check("并行账号数默认 2，范围限制 1-5", normalize_max_accounts("bad") == 2 and normalize_max_accounts(9) == 5 and normalize_max_accounts(0) == 1)

    with tempfile.TemporaryDirectory() as tmp:
        cfg = {
            "automation_data_dir": tmp,
            "accounts": [],
        }
        account_a = {
            "name": "账号A",
            "debug_port": 9301,
            "browser_auto_dir": "",
            "browser_source_user_data": r"C:\ChromeData",
            "browser_source_profile": "Profile 1",
            "jinniu_account_id": "1001",
        }
        account_b = {
            "name": "账号B",
            "debug_port": 9301,
            "browser_auto_dir": "",
            "browser_source_user_data": r"C:\ChromeData",
            "browser_source_profile": "Profile 1",
            "jinniu_account_id": "1001",
        }
        problems = preflight_parallel(cfg, [account_a, account_b])
        check(
            "并行预检能发现重复端口、重复登录配置和重复金牛账户ID",
            any("端口" in item for item in problems)
            and any("登录" in item for item in problems)
            and any("金牛" in item for item in problems),
            str(problems),
        )
        account_b["debug_port"] = 9302
        account_b["browser_source_profile"] = "Profile 2"
        account_b["jinniu_account_id"] = "1002"
        check("并行预检通过独立配置", preflight_parallel(cfg, [account_a, account_b]) == [], str(problems))

    active = {"now": 0, "max": 0}
    lock = threading.Lock()

    def worker(item):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.08)
        with lock:
            active["now"] -= 1
        if item == "bad":
            raise RuntimeError("模拟失败")
        return item

    results, errors = run_parallel_jobs(["a", "b", "c", "bad"], worker, max_workers=2)
    check(
        "并行调度最多同时运行 N 个账号",
        active["max"] <= 2 and sorted(results) == ["a", "b", "c"] and len(errors) == 1,
        "max=%s results=%s errors=%s" % (active["max"], results, errors),
    )


def test_concurrent_state_and_pending_writes() -> None:
    import threading

    from .pending import PendingRenameStore

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        state = RunState.load(run_dir, "2026-09-23")

        def write_state(worker_index):
            for item_index in range(10):
                state.mark(
                    "账号%d" % worker_index,
                    item_index,
                    path=r"G:\素材\账号%d_%d.mp4" % (worker_index, item_index),
                    publish_status="已发布",
                )

        threads = [threading.Thread(target=write_state, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        reloaded = RunState.load(run_dir, "2026-09-23")
        check("并行写入状态文件不会丢记录", len(reloaded.items()) == 40, str(len(reloaded.items())))

        store = PendingRenameStore(run_dir / "pending_rename.json").load()

        def write_pending(worker_index):
            for item_index in range(10):
                store.add("账号%d" % worker_index, "视频%d.mp4" % item_index, "广告语", "")

        threads = [threading.Thread(target=write_pending, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        check("并行写入待改名台账不会丢记录", len(store.entries()) == 40, str(len(store.entries())))


def test_rename_grouping_and_mismatch() -> None:
    """改名前的分组、顺序换算与"条数对不上"的四种处理。"""
    from .flow_jinniu import (
        count_matches,
        decide_mismatch,
        group_by_copy,
        item_for_row,
        targets_for_rows,
    )
    from .flow_jinniu import FALLBACK as JINNIU_KEYS

    items = [
        (0, "同一条广告语", "视频1.mp4"),
        (1, "同一条广告语", "视频2.mp4"),
        (2, "同一条广告语", "视频3.mp4"),
        (3, "另一句广告语", "视频4.mp4"),
    ]
    groups = group_by_copy(items)
    check("相同广告语会并成一组", len(groups) == 2 and len(groups[0]["items"]) == 3, str([len(g["items"]) for g in groups]))
    names = ["素材A", "素材B", "素材C"]
    targets = targets_for_rows(names, groups[0], "newest_first")
    check(
        "列表最新在上时，按文件夹倒序对应",
        targets == ["视频3.mp4", "视频2.mp4", "视频1.mp4"],
        str(targets),
    )
    direct = targets_for_rows(names, groups[0], "oldest_first")
    check("列表最早在上时按文件夹正序对应", direct == ["视频1.mp4", "视频2.mp4", "视频3.mp4"], str(direct))
    check("列表第 1 行对应文件夹最后一条", item_for_row(groups[0], 0, "newest_first")[1] == "视频3.mp4")
    check("查到 1 条时按名字匹配计数", count_matches("同一条广告语", ["同一条广告语-素材"], 1) == 1)
    check("批量组按查到的条数计数", count_matches("同一条广告语", names, 3) == 3)

    class FakeBridge:
        def __init__(self, answer: str) -> None:
            self.answer = answer

        def rescue(self, title, message, options):
            return self.answer

    cfg = {"jinniu": {"on_mismatch": "ask"}}
    check(
        "条数不一致时默认直接继续（不再弹窗打断）",
        decide_mismatch(FakeBridge("任意回答"), "广告语", 1, 3, cfg) == "continue",
    )
    check(
        "配置成自动跳过时跳过",
        decide_mismatch(FakeBridge("任意回答"), "广告语", 1, 3, {"jinniu": {"on_mismatch": "skip"}}) == "skip",
    )
    check(
        "配置成自动重试时重试",
        decide_mismatch(FakeBridge("任意回答"), "广告语", 1, 3, {"jinniu": {"on_mismatch": "retry"}}) == "retry",
    )
    keys = (
        "filter_field_select",
        "filter_field_selected",
        "filter_field_option",
        "search_button",
        "search_input",
        "search_box",
        "row_thumbnail",
        "preview_video",
        "preview_close",
    )
    check("筛选字段与查询用到的候选规则齐全", all(key in JINNIU_KEYS for key in keys))


def test_republish_after_wrong_mark() -> None:
    """回归：被误判成"已发布"的文件，必须能一键清掉并重新发布。"""
    from .state import RunState

    with tempfile.TemporaryDirectory() as tmp:
        state = RunState.load(Path(tmp), "2026-09-16")
        path = r"G:\测试2\素材1.mp4"
        state.item("账号A", 0, "素材1.mp4", "广告语", path)
        state.mark("账号A", 0, path=path, publish_status="已发布")
        check("先确认它被记录成已发布", state.is_published_path("账号A", path))
        removed = state.clear_paths("账号A", [path])
        check("清掉误判记录后会重新发布", removed == 1 and not state.is_published_path("账号A", path), str(removed))
        reloaded = RunState.load(Path(tmp), "2026-09-16")
        check("清理结果已存盘", not reloaded.is_published_path("账号A", path))


def test_library_url_assembly() -> None:
    """回归：金牛地址必须按账号拼 accountId，公共地址里不能写死。"""
    from .config import build_library_url, strip_account_id

    base = "https://niu.e.kuaishou.com/material/supervideo"
    cfg = {"jinniu": {"video_library_url": base + "?__accountId__=111&x=1"}}
    check(
        "公共地址里的 accountId 会被去掉",
        strip_account_id(base + "?__accountId__=111&x=1") == base + "?x=1",
        strip_account_id(base + "?__accountId__=111&x=1"),
    )
    check("去掉后只剩问号时也会清理干净", strip_account_id(base + "?__accountId__=111") == base)
    url = build_library_url(cfg, {"jinniu_account_id": "12345678"})
    check("按账号拼出正确的 accountId", "12345678" in url and "111" not in url, url)
    url2 = build_library_url({"jinniu": {"video_library_url": base}}, {"jinniu_account_id": "8888"})
    check("公共地址没有参数时会自动加 ?", url2.endswith("?__accountId__=8888"), url2)
    url3 = build_library_url(cfg, {})
    check("账号没填 ID 时保留公共地址原样", url3 == cfg["jinniu"]["video_library_url"], url3)


def test_account_chooser() -> None:
    """回归：从金牛地址里取账号 ID（不同账号 accountId 不同）。"""
    from .flow_jinniu import extract_account_id

    check(
        "能从地址里取出账号 ID",
        extract_account_id("https://niu.e.kuaishou.com/material/supervideo?__accountId__=12345678&x=1") == "12345678",
    )
    check("没有账号 ID 时返回空", extract_account_id("https://niu.e.kuaishou.com/material/supervideo") == "")
    check("空地址不报错", extract_account_id("") == "")
    keys = ("account_chooser", "account_chooser_row", "account_chooser_enter")
    from .flow_jinniu import FALLBACK as JINNIU_KEYS

    check("选择账户浮层的候选规则齐全", all(key in JINNIU_KEYS for key in keys))


def test_config_bundle() -> None:
    """回归：导出的配置里不能带本机路径（换电脑后要靠自动探测）。"""
    import json
    import shutil

    from .ui import AutoApp

    path = cfgmod.CONFIG_PATH
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        app = AutoApp()
        app.root.withdraw()
        keys = app.settings_tab.MACHINE_KEYS
        check("导出时会剔除本机浏览器路径字段", "browser_exe" in keys and "browser_auto_dir" in keys)
        account = (app.cfg.get("accounts") or [{}])[0]
        check("当前配置里确实存在这些本机字段（会被剔除）", "browser_exe" in account)
        app.root.destroy()
    except Exception as exc:
        check("导出时会剔除本机浏览器路径字段", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        if backup is not None:
            path.write_text(backup, encoding="utf-8")


def test_wrong_page_protection() -> None:
    """回归：复用上次留下的窗口时，必须识别出"当前不在发布页"。"""
    from .flow_creator import same_site

    publish = "https://cp.kuaishou.com/article/publish/video"
    check("停在金牛页面时会被判定为不在发布页", not same_site("https://niu.e.kuaishou.com/material/supervideo", publish))
    check("停在发布页时判定为正确", same_site(publish, publish))
    check("空白页会被判定为不在发布页", not same_site("about:blank", publish))
    check("没配置网址时不拦截", same_site("about:blank", ""))


def test_popup_and_url_cleanup() -> None:
    """回归：地址里只有一个 accountId；弹窗关闭规则齐全。"""
    from .config import build_library_url
    from .flow_jinniu import FALLBACK as JINNIU_KEYS

    doubled = "https://niu.e.kuaishou.com/material/supervideo?__accountId__=&__accountId__=12345678"
    url = build_library_url({"jinniu": {"video_library_url": doubled}}, {"jinniu_account_id": "12345678"})
    check("地址里只会保留一个 accountId", url.count("__accountId__") == 1, url)
    check("保留的是真实账号 ID", "12345678" in url, url)
    check("弹窗关闭的候选规则齐全", "popup_close" in JINNIU_KEYS and bool(JINNIU_KEYS["popup_close"]))
    check(
        "金牛活动弹窗有自定义关闭图标规则",
        any(
            "icon___" in str(item) and "data-adview" in str(item)
            for item in (JINNIU_KEYS.get("popup_close") or [])
        ),
        str(JINNIU_KEYS.get("popup_close")),
    )


def test_dismiss_popup_really_closes() -> None:
    """回归：弹窗 click() 后必须回读确认弹窗消失，不能只调用一次就当成功。"""
    import logging

    from .flow_jinniu import dismiss_popups
    from .selectors import Selectors

    class State:
        open = True
        clicks = 0

    class PopupLocator:
        def __init__(self, state):
            self.state = state

        @property
        def first(self):
            return self

        def count(self):
            return 1 if self.state.open else 0

        def is_visible(self):
            return self.state.open

        def click(self, timeout=0, force=False):
            self.state.clicks += 1
            self.state.open = False

    class FakePage:
        def __init__(self, state):
            self.state = state
            self.keyboard = self

        def locator(self, _css):
            return PopupLocator(self.state)

        def press(self, _key):
            return None

        def wait_for_timeout(self, _ms):
            return None

    class Ctx:
        def __init__(self, state):
            self.page = FakePage(state)
            self.logger = logging.getLogger("selftest.popup")
            self.selectors = Selectors.load()

    state = State()
    closed = dismiss_popups(Ctx(state), rounds=2)
    check("弹窗关闭后会回读确认已消失", closed == 1 and state.open is False and state.clicks >= 1, "closed=%s clicks=%s open=%s" % (closed, state.clicks, state.open))


def test_mark_state_smoke() -> None:
    """回归：mark_state 必须能正常调用（不能自递归/重复参数，且记录失败不能抛异常）。"""
    import tempfile

    import app.flow_jinniu as flow
    from app.state import RunState

    class Video:
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

    class Logger:
        def info(self, *a, **k):
            return None

        def warning(self, *a, **k):
            return None

    class Ctx:
        def __init__(self, state):
            self.account = {"name": "账号A"}
            self.videos = [Video(r"G:\测试\a.mp4")]
            self.state = state
            self.logger = Logger()

    with tempfile.TemporaryDirectory() as tmp:
        state = RunState.load(Path(tmp), "2026-09-18")
        ctx = Ctx(state)
        try:
            flow.mark_state(ctx, 0, rename_status="已改名")
            ok = state.is_renamed("账号A", 0) or state.items()
            check("mark_state 能正常写入状态", bool(ok), str(state.items()))
        except Exception as exc:
            check("mark_state 能正常写入状态", False, "%s: %s" % (type(exc).__name__, exc))


def test_state_key_by_path() -> None:
    """回归：换了素材文件夹后，同序号的新视频不能再被判成"已发布"。"""
    from .state import RunState

    with tempfile.TemporaryDirectory() as tmp:
        state = RunState.load(Path(tmp), "2026-09-18")
        state.item("账号A", 0, "甲.mp4", "广告语", r"G:\旧文件夹\甲.mp4")
        state.mark("账号A", 0, path=r"G:\旧文件夹\甲.mp4", publish_status="已发布")
        check("旧文件夹的文件仍算已发布", state.is_published_path("账号A", r"G:\旧文件夹\甲.mp4"))
        state.item("账号A", 0, "乙.mp4", "广告语", r"G:\新文件夹\乙.mp4")
        check(
            "换文件夹后，新文件不再被误判为已发布",
            not state.is_published_path("账号A", r"G:\新文件夹\乙.mp4"),
        )
        check("换文件夹不会覆盖旧记录", state.is_published_path("账号A", r"G:\旧文件夹\甲.mp4"))
        check("两条记录各自独立存在", len(state.items()) == 2, str(len(state.items())))


def test_two_level_matching() -> None:
    """回归：时长相同的多条素材，按"上传先后 ↔ 文件夹顺序"依次配对。"""
    import app.flow_jinniu as flow

    class Video:
        def __init__(self, name: str) -> None:
            self.name = name

        def __str__(self) -> str:
            return self.name

    class Logger:
        def info(self, *args, **kwargs):
            return None

    class Ctx:
        jinniu = {"duration_tolerance_seconds": 1}
        videos = [Video("A_1.mp4"), Video("A_2.mp4"), Video("A_3.mp4"), Video("B_1.mp4")]
        logger = Logger()

    durations_map = {"A_1.mp4": 20.0, "A_2.mp4": 20.0, "A_3.mp4": 20.0, "B_1.mp4": 35.0}
    original = flow.duration_seconds
    flow.duration_seconds = lambda path: durations_map.get(str(path))
    try:
        group = {"items": [(0, "A_1.mp4"), (1, "A_2.mp4"), (2, "A_3.mp4"), (3, "B_1.mp4")]}
        got = flow.match_targets_two_level(
            Ctx(), group, [20.0, 20.0, 20.0, 35.0], [300.0, 200.0, 100.0, 50.0]
        )
        check(
            "时长相同的素材按上传先后对应文件夹顺序",
            got == ["A_3.mp4", "A_2.mp4", "A_1.mp4", "B_1.mp4"],
            str(got),
        )
        unique = flow.match_targets_two_level(Ctx(), group, [35.0, None, None, None], [None] * 4)
        check("唯一时长的那条精确配对", unique[0] == "B_1.mp4", str(unique))
    finally:
        flow.duration_seconds = original


def test_fallback_keyword() -> None:
    """兜底查询关键词：从 12 字起，延伸到下一个标点之前（避免把标点带进关键词）。"""
    from .flow_jinniu import build_fallback_keyword

    text = "新手闭眼入！怎么刷都不苍蝇腿、不晕妆，防水防泪持久卷翘，根根分明一整天！#三资堂"
    keyword = build_fallback_keyword(text, 12)
    check("第 13 个字不是标点时，延伸到下一个标点之前", keyword == "新手闭眼入！怎么刷都不苍蝇腿", keyword)
    check("关键词里不含标点（除开头已有的）", "、" not in keyword and "，" not in keyword, keyword)
    check("第 13 个字就是标点时只用 12 个字", build_fallback_keyword("一二三四五六七八九十十一，后面还有字", 12) == "一二三四五六七八九十十一")
    check("短文本原样返回", build_fallback_keyword("很短的一句话", 12) == "很短的一句话")
    none_punct = "一二三四五六七八九十十一十二十三十四十五"
    check("整句没有标点时返回整句", build_fallback_keyword(none_punct, 12) == none_punct)


def test_creation_time_alignment() -> None:
    """按「创建时间」对齐：最早创建的素材 = 文件夹里的第一条视频。"""
    from .flow_jinniu import build_targets_for_group, read_row_creations
    from .selectors import Selectors

    class FakeCell:
        def __init__(self, text: str) -> None:
            self.text = text

        def inner_text(self):
            return self.text

    class FakeRows:
        def __init__(self, texts) -> None:
            self.texts = texts

        @property
        def first(self):
            return self

        def count(self):
            return len(self.texts)

        def nth(self, index):
            return FakeCell(self.texts[index])

        def is_visible(self):
            return True

    class FakePage:
        def __init__(self, texts) -> None:
            self.texts = texts

        def locator(self, selector):
            return FakeRows(self.texts)

        def get_by_text(self, text, exact=False):
            return FakeRows([])

        def get_by_placeholder(self, text):
            return FakeRows([])

    class FakeLogger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

    class FakeCtx:
        def __init__(self, texts) -> None:
            self.page = FakePage(texts)
            self.selectors = Selectors.load()
            self.logger = FakeLogger()
            self.cfg = {}
            self.jinniu = {}

    rows = [
        "素材A ID:1 2026-09-16 16:50:51",
        "素材B ID:2 2026-09-16 16:48:12",
        "素材C ID:3 2026-09-16 16:46:51",
    ]
    ctx = FakeCtx(rows)
    group = {"copy": "广告语", "items": [(0, "视频1.mp4"), (1, "视频2.mp4"), (2, "视频3.mp4")]}
    names = ["素材A", "素材B", "素材C"]
    targets = build_targets_for_group(ctx, group, names, "newest_first")
    check(
        "按创建时间对齐（最新的行对应文件夹里最后一条）",
        targets == ["视频3.mp4", "视频2.mp4", "视频1.mp4"],
        str(targets),
    )
    creations = read_row_creations(ctx, 3)
    check("每行的创建时间都能读出来", all(item is not None for item in creations))
    no_time = FakeCtx(["素材A 无时间", "素材B 无时间", "素材C 无时间"])
    fallback = build_targets_for_group(no_time, group, names, "newest_first")
    check("读不到创建时间时退回列表顺序规则", fallback == ["视频3.mp4", "视频2.mp4", "视频1.mp4"], str(fallback))


def test_video_duration() -> None:
    """时长校验：页面上的 mm:ss 与本地 mp4 的 mvhd 都要能读出来。"""
    import struct

    from .videometa import duration_seconds, extract_duration_seconds

    check("能从页面文字里读出时长（00:15）", extract_duration_seconds("素材A 00:15 2026-09-16") == 15)
    check("能从页面文字里读出时长（1:23）", extract_duration_seconds("1:23") == 83)
    check("文字里没有时长时返回空", extract_duration_seconds("素材A 已审核") is None)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "样本.mp4"
        mvhd = (
            struct.pack(">I4s", 108, b"mvhd")
            + b"\x00" * 4
            + b"\x00" * 8
            + struct.pack(">II", 1000, 15000)
            + b"\x00" * 80
        )
        moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
        mdat = struct.pack(">I4s", 16, b"mdat") + b"0" * 8
        path.write_bytes(mdat + moov)
        value = duration_seconds(path)
        check("能读出本地视频时长（15 秒）", value is not None and abs(value - 15.0) < 0.01, str(value))


def test_title_already_filled() -> None:
    """回归：上传完成后标题若已在位，不应重复填写。"""
    from .flow_creator import current_title, title_is_complete, title_matches
    from .selectors import Selectors

    class FakeLocator:
        def __init__(self, text: str) -> None:
            self.text = text

        @property
        def first(self):
            return self

        def count(self):
            return 1

        def is_visible(self):
            return True

        def inner_text(self):
            return self.text

        def input_value(self):
            return self.text

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def locator(self, selector):
            return FakeLocator(self.text)

        def get_by_text(self, text, exact=False):
            return FakeLocator("")

        def get_by_placeholder(self, text):
            return FakeLocator("")

    class FakeCtx:
        def __init__(self, text: str) -> None:
            self.page = FakePage(text)
            self.selectors = Selectors.load()
            self.creator = {}

    copy_text = "新手闭眼入！怎么刷都不苍蝇腿、不晕妆"
    filled = FakeCtx("新手闭眼入！怎么刷都不苍蝇腿、不晕妆 #示例品牌 #示例账号")
    check("标题已在位时会被识别（不重复填写）", title_matches(filled, copy_text))
    check("读取到的标题文字正确", current_title(filled).startswith("新手闭眼入"))
    empty = FakeCtx("")
    check("标题为空时判定为未填写", not title_matches(empty, copy_text))
    other = FakeCtx("完全不同的另一句话")
    check("标题是别的内容时判定为未填写", not title_matches(other, copy_text))
    full = "新手闭眼入！怎么刷都不苍蝇腿、不晕妆 #示例品牌 #示例账号"
    check("标题完整时校验通过（含自动追加的话题）", title_is_complete(full, copy_text))
    cut = "新手闭眼入！怎么刷都不苍"
    check("标题被截断时校验不通过（不会被误判为填好）", not title_is_complete(cut, copy_text))
    check("空标题校验不通过", not title_is_complete("", copy_text))


def test_dry_run_pipeline() -> None:
    """用假的浏览器把「仅演练」整条流程跑一遍：漏定义/漏导入会在这里立刻暴露。"""
    path = cfgmod.CONFIG_PATH
    backup = path.read_text(encoding="utf-8") if path.exists() else None
    tmp = Path(tempfile.mkdtemp())
    try:
        from . import ui as ui_module
        from .ui import AutoApp

        ui_module.cfgmod.RUN_DIR = tmp / "runs"
        app = AutoApp()
        app.root.withdraw()
        app.report_dir = tmp / "reports"
        app.bridge.confirm_table = lambda *a, **k: True
        app.bridge.confirm = lambda *a, **k: True
        calls = {}

        class FakePage:
            url = "about:blank"

            def wait_for_timeout(self, *a, **k):
                return None

            def is_closed(self):
                return False

            def bring_to_front(self):
                return None

        class FakeBrowser:
            def __init__(self, *a, **k):
                self.page = FakePage()
                self.reuse_login = True

            def start(self, *a, **k):
                return self

            def close(self):
                return None

        ui_module.AccountBrowser = FakeBrowser
        ui_module.run_creator_account = lambda ctx: calls.setdefault("creator", True)
        ui_module.run_jinniu_account = lambda ctx: calls.setdefault("jinniu", True)

        video = tmp / "测试素材1.mp4"
        video.write_bytes(b"0" * 1024)
        account = app.cfg["accounts"][0] if app.cfg.get("accounts") else cfgmod.default_account(0)
        account["enabled"] = True
        app.stop_event.clear()
        app._run_worker("dry", [(account, [video], ["测试广告语"])])
        check("「仅演练」整条流程能跑完不报错", calls.get("creator") is True, str(calls))
        app.root.destroy()
    except Exception as exc:
        check("「仅演练」整条流程能跑完不报错", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        if backup is not None:
            path.write_text(backup, encoding="utf-8")


def test_chrome_profile_detection() -> None:
    from .browser import list_chrome_profiles

    root = cfgmod.expand_path(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    profiles = list_chrome_profiles(root)
    if not Path(root).is_dir():
        check("能读取 Chrome 配置列表（本机没装 Chrome 时跳过）", True, "skipped")
        return
    names = ", ".join("%s(%s)" % (dir_name, display) for dir_name, display in profiles[:6])
    check("能读取 Chrome 配置列表", len(profiles) >= 1, names)
    print("    发现的 Chrome 配置：%s" % (names or "无"))


def main() -> int:
    print("=" * 62)
    print("快手自动发布助手 · 离线自检（不会打开浏览器、不会操作账号）")
    print("=" * 62)
    test_natural_sort()
    test_copy_parsing()
    test_state_resume()
    test_report()
    test_publish_settings_model()
    test_pending_rename_store()
    test_publish_config_and_selectors()
    test_report_publish_columns()
    test_state_transient_publish_fields()
    test_parallel_preflight_and_scheduler()
    test_concurrent_state_and_pending_writes()
    test_config_roundtrip()
    test_browser_and_login_options()
    test_copy_store()
    test_batch_copies_and_lean_copy()
    test_attached_page()
    test_dry_run_pipeline()
    test_skip_by_full_path()
    test_rename_grouping_and_mismatch()
    test_republish_after_wrong_mark()
    test_title_already_filled()
    test_video_duration()
    test_creation_time_alignment()
    test_fallback_keyword()
    test_two_level_matching()
    test_state_key_by_path()
    test_mark_state_smoke()
    test_popup_and_url_cleanup()
    test_dismiss_popup_really_closes()
    test_wrong_page_protection()
    test_config_bundle()
    test_account_chooser()
    test_library_url_assembly()
    test_card_status_states()
    test_selector_engine()
    test_jinniu_order()
    test_ui_import()
    test_settings_roundtrip_keeps_login()
    test_settings_and_cards_ownership()
    test_chrome_profile_detection()
    failed = [name for name, ok, _ in RESULTS if not ok]
    print("-" * 62)
    print("共 %d 项，通过 %d 项，失败 %d 项" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        print("失败项：" + "；".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
