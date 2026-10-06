"""设计路线只表示本次任务里的互补策略，不绑定特定软件或商品名。"""

from __future__ import annotations

import re
from typing import List


def default_routes() -> List[dict]:
    return [
        {
            "id": "route_a",
            "prefix": "A",
            "name": "路线A",
            "title": "路线A",
            "focus": "偏膜近端、内化表位和不同分子格式，CDR-H3 长度拉开。这是设计策略，不是某个计算软件的输出。",
        },
        {
            "id": "route_b",
            "prefix": "B",
            "name": "路线B",
            "title": "路线B",
            "focus": "偏功能表位覆盖、效应功能相关格式和特异性机制，与路线A的 CDR-H3、表位侧重点不要雷同。不要把结果写成用户未指定的软件或商品输出。",
        },
    ]


def normalize_routes(raw_routes: List[dict]) -> List[dict]:
    normalized = []
    seen_prefix = set()
    for index, raw in enumerate(raw_routes, start=1):
        name = str(raw.get("name") or raw.get("expert") or raw.get("title") or f"路线{index}").strip()
        title = str(raw.get("title") or name).strip() or name
        prefix = re.sub(r"[^A-Za-z0-9]+", "", str(raw.get("prefix") or "")).upper()[:8]
        if not prefix or prefix in seen_prefix:
            prefix = f"R{index}"
            while prefix in seen_prefix:
                prefix = f"R{index}{len(seen_prefix)}"
        seen_prefix.add(prefix)
        normalized.append(
            {
                "id": str(raw.get("id") or f"route_{index}").strip() or f"route_{index}",
                "prefix": prefix,
                "name": name,
                "title": title,
                "expert": name,
                "focus": str(raw.get("focus") or "").strip(),
            }
        )
    return normalized


def routes_from_candidates(candidates: List) -> List[dict]:
    found: List[dict] = []
    seen = set()
    for candidate in candidates:
        prefix = getattr(candidate, "route_label", "") or ""
        if not prefix or prefix in seen:
            continue
        seen.add(prefix)
        name = getattr(candidate, "expert", "") or getattr(candidate, "route", "") or prefix
        found.append(
            {
                "id": f"route_{len(found) + 1}",
                "prefix": prefix,
                "name": name,
                "title": getattr(candidate, "route", "") or name,
                "expert": name,
                "focus": "",
            }
        )
    return found or default_routes()


def route_label_text(routes: List[dict]) -> str:
    names = [item.get("name") or item.get("prefix") or "" for item in routes]
    return "、".join(name for name in names if name) or "未命名路线"
