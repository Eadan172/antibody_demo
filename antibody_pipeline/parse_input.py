"""从用户需求文本中提取可以确定解析的字段。

自由叙述仍交给大模型理解。计算软件地址、候选数量和明确列出的靶点
在这里解析，避免路径被模型改写。
"""

from __future__ import annotations

import re
from typing import Dict, List

from antibody_pipeline.models import ComputeTool

SECTION_NAMES = (
    "项目名称",
    "任务",
    "指定靶点",
    "种属与交叉",
    "种属",
    "理化与可开发性",
    "理化性质",
    "分子格式",
    "功能模态",
    "计算软件",
    "每路线每靶点候选数",
)

_HEADER = re.compile(
    r"^\s*(?P<name>" + "|".join(SECTION_NAMES) + r")\s*[:：]?\s*$"
)


def split_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current = ""
    for line in text.splitlines():
        match = _HEADER.match(line.strip())
        if match:
            current = match.group("name")
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _clean_item(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*•]\s*", "", line)
    return line.strip()


def _is_comment(line: str) -> bool:
    stripped = line.strip()
    return (not stripped) or stripped.startswith("#") or stripped.startswith("（") or stripped.startswith("(")


def parse_targets(section: str) -> List[str]:
    names = []
    for raw in section.splitlines():
        if _is_comment(raw):
            continue
        item = _clean_item(raw)
        if not item:
            continue
        if "留空" in item or item.startswith("若"):
            continue
        names.append(item)
    return names


def parse_count(section: str, fallback_text: str, default: int) -> int:
    for source in (section, fallback_text):
        if not source:
            continue
        match = re.search(r"(\d+)", source if source == section else "")
        if source == section and match:
            value = int(match.group(1))
            if 1 <= value <= 12:
                return value
        match = re.search(
            r"每(?:条路线)?(?:每(?:个)?靶点)?(?:设计|候选)?\s*(\d+)\s*条",
            source,
        )
        if match:
            value = int(match.group(1))
            if 1 <= value <= 12:
                return value
    return default


def parse_compute_tools(section: str) -> List[ComputeTool]:
    tools: List[ComputeTool] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in re.split(r"[|｜]", line)]
        if len(parts) < 3:
            continue
        name, kind, address = parts[0], parts[1].lower(), parts[2]
        command = parts[3] if len(parts) > 3 else ""
        token = parts[4] if len(parts) > 4 else ""
        if not name or not address:
            continue
        if kind in {"cli", "本地", "local", "bin", "exe"}:
            kind = "cli"
        elif kind in {"api", "http", "接口", "url"}:
            kind = "api"
        else:
            continue
        tools.append(
            ComputeTool(
                name=name,
                kind=kind,
                address=address,
                command=command,
                token=token,
            )
        )
    return tools


def slug_target(name: str) -> str:
    # B7-H3（CD276）→ 优先用括号外的主名
    main = re.split(r"[（(]", name, maxsplit=1)[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "", main).upper()
    return slug[:16] or "TGT"


def parse_requirement_hints(text: str, default_n: int) -> dict:
    sections = split_sections(text)
    targets = parse_targets(sections.get("指定靶点", ""))
    count = parse_count(
        sections.get("每路线每靶点候选数", ""),
        text,
        default_n,
    )
    project = ""
    if sections.get("项目名称"):
        for raw in sections["项目名称"].splitlines():
            if raw.strip() and not raw.strip().startswith("#"):
                project = _clean_item(raw)
                break
    return {
        "project_name": project or "抗体候选设计",
        "task_text": sections.get("任务", "").strip(),
        "targets": targets,
        "n_per_route_per_target": count,
        "species_text": sections.get("种属与交叉") or sections.get("种属") or "",
        "physicochemical_text": sections.get("理化与可开发性") or sections.get("理化性质") or "",
        "formats_text": sections.get("分子格式", ""),
        "modalities_text": sections.get("功能模态", ""),
        "compute_tools": parse_compute_tools(sections.get("计算软件", "")),
        "sections": sections,
    }
