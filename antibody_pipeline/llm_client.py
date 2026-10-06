"""OpenAI 兼容聊天接口。"""

from __future__ import annotations

import time
from typing import Any, Optional

from antibody_pipeline.jsonutil import JsonParseError, extract_json


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.4,
        timeout: int = 180,
        max_tokens: int = 12000,
    ) -> None:
        if not api_key:
            raise LLMError("缺少 LLM_API_KEY")
        from openai import OpenAI

        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat(self, system: str, user: str, temperature: Optional[float] = None) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                return self._complete(messages, temperature, use_max_tokens=True)
            except Exception as exc:  # 网络、参数、限流都在这里重试
                last_error = exc
                text = str(exc).lower()
                if "max_tokens" in text or "max_completion_tokens" in text:
                    try:
                        return self._complete(messages, temperature, use_max_tokens=False)
                    except Exception as inner:
                        last_error = inner
                time.sleep(2 ** attempt)
        raise LLMError(f"大模型调用失败：{last_error}")

    def _complete(self, messages: list, temperature: Optional[float], use_max_tokens: bool) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if use_max_tokens and self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
        response = self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise LLMError("模型返回空内容")
        return content

    def chat_json(self, system: str, user: str, temperature: Optional[float] = None) -> Any:
        last_error: Optional[Exception] = None
        prompt = user
        for _ in range(2):
            text = self.chat(system, prompt, temperature=temperature)
            try:
                return extract_json(text)
            except JsonParseError as exc:
                last_error = exc
                prompt = (
                    user
                    + "\n\n上一次回复无法解析为 JSON。请只输出一个 JSON 对象，不要 Markdown 说明。"
                )
        raise LLMError(f"模型没有返回可解析的 JSON：{last_error}")
