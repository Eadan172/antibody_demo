"""显式配置的本地程序与 HTTP 计算接口适配器。"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ToolSpec


def run_tools(
    specs: list[ToolSpec],
    *,
    task_file: Path,
    output_dir: Path,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    tool_dir = output_dir / "computations"
    tool_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in specs:
        started = datetime.now(timezone.utc).isoformat()
        try:
            if spec.kind == "local":
                result = _run_local(spec, task_file, output_dir, tool_dir)
            else:
                result = _run_api(spec, context, tool_dir)
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}
        result.update({"name": spec.name, "kind": spec.kind, "started_at": started})
        results.append(result)

    (tool_dir / "manifest.json").write_text(
        json.dumps(
            {"tools": [asdict(spec) for spec in specs], "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results


def _run_local(
    spec: ToolSpec, task_file: Path, output_dir: Path, tool_dir: Path
) -> dict[str, Any]:
    if not spec.command:
        raise ValueError("未配置 command")
    rendered = spec.command.format(
        input=str(task_file.resolve()),
        output_dir=str(tool_dir.resolve()),
        project_dir=str(Path.cwd().resolve()),
    )
    command = shlex.split(rendered)
    completed = subprocess.run(
        command,
        cwd=output_dir,
        text=True,
        capture_output=True,
        timeout=spec.timeout,
        check=False,
    )
    stem = _safe_name(spec.name)
    (tool_dir / f"{stem}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (tool_dir / f"{stem}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "stdout_file": f"computations/{stem}.stdout.txt",
        "stderr_file": f"computations/{stem}.stderr.txt",
        "stdout_preview": completed.stdout[:20000],
        "stderr_preview": completed.stderr[:5000],
    }


def _run_api(
    spec: ToolSpec, context: dict[str, Any], tool_dir: Path
) -> dict[str, Any]:
    if not spec.url:
        raise ValueError("未配置 url")
    payload = json.dumps(context, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    headers.update({key: os.path.expandvars(value) for key, value in spec.headers.items()})
    request = urllib.request.Request(
        spec.url,
        data=payload if spec.method != "GET" else None,
        method=spec.method,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=spec.timeout) as response:
        raw = response.read()
        status_code = response.status
        content_type = response.headers.get("Content-Type", "")
    suffix = ".json" if "json" in content_type else ".txt"
    result_file = tool_dir / f"{_safe_name(spec.name)}{suffix}"
    result_file.write_bytes(raw)
    return {
        "status": "completed",
        "http_status": status_code,
        "result_file": f"computations/{result_file.name}",
        "result_preview": raw.decode("utf-8", errors="replace")[:20000],
    }


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
