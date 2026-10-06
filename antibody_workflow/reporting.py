"""Markdown、HTML 与审计文件生成。"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


DISCLAIMER = (
    "> **证据边界**：公开事实仅以列出的可核验文献为依据；模型分析与候选设计"
    "属于 in-silico 假设；本地/API 工具未返回的指标均标记为“未计算”。"
    "任何候选均须经结构计算、体外实验及安全性验证。"
)


def write_markdown(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    body = [f"# {title}", "", DISCLAIMER, ""]
    for heading, content in sections:
        body.extend([f"## {heading}", "", content.strip() or "未提供。", ""])
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def value_to_markdown(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if not value:
            return "无。"
        return "\n".join(
            f"{index}. {item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)}"
            for index, item in enumerate(value, 1)
        )
    if isinstance(value, dict):
        return "\n".join(
            f"- **{key}**：{item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)}"
            for key, item in value.items()
        )
    return str(value)


def markdown_to_html(markdown: str, title: str) -> str:
    """生成无外部依赖、可直接打开的简洁 HTML。"""
    blocks: list[str] = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            blocks.append("</ul>")
            in_list = False
        if line.startswith("### "):
            blocks.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            blocks.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("> "):
            blocks.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line:
            blocks.append(f"<p>{_inline(line)}</p>")
    if in_list:
        blocks.append("</ul>")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;line-height:1.7;color:#172033}}
h1,h2,h3{{color:#123b63}} blockquote{{background:#fff6d8;border-left:4px solid #d8a600;padding:12px}}
code{{background:#eef2f6;padding:2px 5px}} li{{margin:5px 0}}
</style></head><body>{''.join(blocks)}</body></html>"""


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" rel="noopener">\1</a>',
        escaped,
    )
    return escaped
