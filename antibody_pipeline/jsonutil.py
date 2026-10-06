"""从模型回复中取出 JSON。"""

from __future__ import annotations

import json
import re
from typing import Any


class JsonParseError(ValueError):
    pass


def extract_json(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise JsonParseError("模型没有返回内容")
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", raw, flags=re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(raw)
    start_obj = raw.find("{")
    end_obj = raw.rfind("}")
    if start_obj >= 0 and end_obj > start_obj:
        candidates.append(raw[start_obj : end_obj + 1])
    start_arr = raw.find("[")
    end_arr = raw.rfind("]")
    if start_arr >= 0 and end_arr > start_arr:
        candidates.append(raw[start_arr : end_arr + 1])
    last_error = None
    for item in candidates:
        try:
            return json.loads(item)
        except json.JSONDecodeError as exc:
            last_error = exc
    raise JsonParseError(f"无法解析 JSON：{last_error}")
