"""OpenAI 兼容的 LLM 客户端，仅依赖 Python 标准库。"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Settings


SYSTEM_PROMPT = """你是抗体发现项目的严谨研究助手。遵守以下规则：
1. 区分公开事实、模型推断、真实计算结果和待实验验证项。
2. 不得虚构文献、DOI、实验值、结构分数、亲和力或候选序列的验证状态。
3. 引用只能来自提供给你的检索记录；记录不足时明确写“待检索/待核验”。
4. 抗体候选及评分只能作为 in-silico 假设，必须给出湿实验验证建议。
5. 所有设计路线、分析对象和候选编号必须从当前需求与证据动态产生；不得沿用案例
   中的公司名、商品名、专有平台名、候选前缀或候选序列。路线使用机制描述，
   候选编号使用“CAND-靶点-序号”一类中性格式。
6. 输出有效 JSON，不要使用 Markdown 代码围栏。"""


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ask_json(
        self,
        prompt: str,
        *,
        schema_hint: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{prompt}\n\n必须返回的 JSON 结构：\n{schema_hint}",
                },
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        endpoint = f"{self.settings.base_url}/chat/completions"
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            request = urllib.request.Request(
                endpoint,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.settings.timeout
                ) as response:
                    result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                return _parse_json_content(content)
            except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt + 1 < self.settings.max_retries:
                    time.sleep((2**attempt) + random.random())

        raise LLMError(f"LLM 请求失败（已重试）: {last_error}") from last_error


def _parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("LLM 响应 content 不是字符串或对象")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON 顶层必须是对象")
    return parsed
