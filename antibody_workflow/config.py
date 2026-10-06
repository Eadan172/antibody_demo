"""运行配置和自然语言任务文件解析。"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolSpec:
    name: str
    kind: str
    command: str = ""
    url: str = ""
    method: str = "POST"
    timeout: int = 900
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskRequest:
    requirements: str
    project_name: str = "antibody-project"
    output_dir: str = "outputs"
    language: str = "zh-CN"
    research_queries: list[str] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: int = 180
    max_retries: int = 3

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Settings":
        load_dotenv((root or Path.cwd()) / ".env")
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "未找到 LLM_API_KEY。请运行 ./setup.sh，或在 .env 中填写该值。"
            )
        return cls(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("LLM_MODEL", "gpt-5-mini"),
            timeout=int(os.getenv("LLM_TIMEOUT", "180")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )


def load_dotenv(path: Path) -> None:
    """加载简单 KEY=VALUE 文件，不覆盖调用者已经设置的环境变量。"""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def parse_task_file(path: Path) -> TaskRequest:
    """解析任务文件。

    文件可以全部是自然语言；也可在开头放置 INI 配置块，使用
    ``---config`` 与 ``---end`` 包围。配置之外的正文均作为需求。
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"任务文件为空: {path}")

    config_text = ""
    requirements = text
    if text.startswith("---config"):
        marker = "\n---end"
        end = text.find(marker)
        if end < 0:
            raise ValueError("任务配置块缺少 ---end")
        config_text = text[len("---config") : end].strip()
        requirements = text[end + len(marker) :].strip()

    parser = configparser.ConfigParser(interpolation=None)
    if config_text:
        parser.read_string(config_text)

    project = parser["project"] if parser.has_section("project") else {}
    request = TaskRequest(
        requirements=requirements,
        project_name=project.get("name", path.stem),
        output_dir=project.get("output_dir", "outputs"),
        language=project.get("language", "zh-CN"),
        research_queries=_split_lines(project.get("research_queries", "")),
    )

    for section in parser.sections():
        if ":" not in section:
            continue
        kind, name = section.split(":", 1)
        if kind not in {"local_tool", "api_tool"}:
            continue
        values = parser[section]
        headers = {
            key.removeprefix("header_").replace("_", "-"): value
            for key, value in values.items()
            if key.startswith("header_")
        }
        request.tools.append(
            ToolSpec(
                name=name.strip(),
                kind="local" if kind == "local_tool" else "api",
                command=values.get("command", ""),
                url=values.get("url", ""),
                method=values.get("method", "POST").upper(),
                timeout=values.getint("timeout", fallback=900),
                headers=headers,
            )
        )
    return request


def _split_lines(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]
