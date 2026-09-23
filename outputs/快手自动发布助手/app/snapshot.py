# -*- coding: utf-8 -*-
"""页面快照：抓取页面结构、截图和可交互元素清单（勘查与诊断共用）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

COLLECT_JS = """
() => {
  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  const clean = (value) => String(value || '').replace(/[\\s\\u00a0]+/g, ' ').trim();
  const nodes = document.querySelectorAll(
    "input,textarea,button,a,[contenteditable=true],[role=button],[class*=upload],[class*=publish],[class*=btn]"
  );
  const elements = [];
  let seq = 0;
  for (const el of nodes) {
    if (!visible(el)) continue;
    const rect = el.getBoundingClientRect();
    elements.push({
      i: seq++,
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      id: el.id || '',
      name: el.getAttribute('name') || '',
      cls: String(el.className || '').slice(0, 140),
      placeholder: el.getAttribute('placeholder') || '',
      aria: el.getAttribute('aria-label') || '',
      title: el.getAttribute('title') || '',
      text: clean(el.innerText || el.value || '').slice(0, 80),
      x: Math.round(rect.x), y: Math.round(rect.y),
      w: Math.round(rect.width), h: Math.round(rect.height)
    });
    if (elements.length >= 400) break;
  }
  const rows = [];
  for (const tr of document.querySelectorAll('tbody tr')) {
    rows.push({
      text: clean(tr.innerText).slice(0, 160),
      html: String(tr.outerHTML || '').slice(0, 600)
    });
    if (rows.length >= 30) break;
  }
  const dialogs = [];
  for (const d of document.querySelectorAll('[role=dialog],[class*=modal],[class*=drawer]')) {
    if (!visible(d)) continue;
    dialogs.push({
      cls: String(d.className || '').slice(0, 160),
      text: clean(d.innerText).slice(0, 400),
      html: String(d.outerHTML || '').slice(0, 1500)
    });
    if (dialogs.length >= 5) break;
  }
  return {elements: elements, rows: rows, dialogs: dialogs};
}
"""


def safe_url(page) -> str:
    try:
        return page.url
    except Exception:
        return ""


def capture(page, folder: Path, tag: str, logger=None) -> Dict[str, Any]:
    """把当前页面存成 截图 + HTML + 元素清单，返回保存信息。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    base = "%s_%s" % (stamp, tag)
    info: Dict[str, Any] = {"folder": str(folder), "files": [], "url": safe_url(page), "title": ""}
    try:
        shot = folder / (base + ".png")
        page.screenshot(path=str(shot), full_page=True)
        info["files"].append(str(shot))
    except Exception as exc:
        info["error"] = "截图失败：%s" % exc
        if logger:
            logger.warning("截图失败：%s", exc)
    try:
        html_file = folder / (base + ".html")
        html_file.write_text(page.content(), encoding="utf-8")
        info["files"].append(str(html_file))
    except Exception as exc:
        if logger:
            logger.warning("保存 HTML 失败：%s", exc)
    try:
        data = page.evaluate(COLLECT_JS)
        data["url"] = info["url"]
        try:
            data["title"] = page.title()
            info["title"] = data["title"]
        except Exception:
            data["title"] = ""
        json_file = folder / (base + ".json")
        json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        info["files"].append(str(json_file))
        info["element_count"] = len(data.get("elements") or [])
    except Exception as exc:
        if logger:
            logger.warning("抓取元素失败：%s", exc)
    return info
