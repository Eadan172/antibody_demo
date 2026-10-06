"""调用用户在需求文件里登记的本地程序或 HTTP 接口。

只记录真实返回。程序不存在、接口失败或结果里没有指标时，不填结构分数。
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from antibody_pipeline.models import Candidate, ComputeTool, ToolRun

METRIC_KEYS = ("iptm", "plddt", "ptm", "pae", "score", "notes")


def _candidate_payload(candidates: List[Candidate]) -> List[dict]:
    payload = []
    for candidate in candidates:
        payload.append(
            {
                "id": candidate.id,
                "target": candidate.target,
                "route": candidate.route,
                "format": candidate.format,
                "vh": candidate.vh,
                "vl": candidate.vl,
            }
        )
    return payload


def _coerce_metrics(item: dict) -> Dict[str, Any]:
    metrics = {}
    for key in METRIC_KEYS:
        if key in item and item[key] not in (None, ""):
            metrics[key] = item[key]
    for key, value in item.items():
        lowered = str(key).lower()
        if lowered in METRIC_KEYS and lowered not in metrics and value not in (None, ""):
            metrics[lowered] = value
    return metrics


def _rows_from_json(data: Any) -> List[dict]:
    if isinstance(data, dict):
        for key in ("results", "predictions", "candidates", "data"):
            if isinstance(data.get(key), list):
                return [row for row in data[key] if isinstance(row, dict)]
        if any(key in data or str(key).lower() in METRIC_KEYS for key in data):
            return [data]
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def parse_metrics(data: Any) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for row in _rows_from_json(data):
        identity = row.get("id") or row.get("name") or row.get("candidate_id") or ""
        identity = str(identity).strip()
        metrics = _coerce_metrics(row)
        if identity and metrics:
            found[identity] = metrics
    return found


def _load_json_text(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _apply(candidates: List[Candidate], metrics_by_id: Dict[str, Dict[str, Any]]) -> None:
    by_id = {candidate.id: candidate for candidate in candidates}
    for identity, metrics in metrics_by_id.items():
        candidate = by_id.get(identity)
        if candidate is None:
            # 允许工具只回传不带 _VH/_VL 的主编号
            stem = identity.split("_")[0]
            candidate = by_id.get(stem)
        if candidate is None:
            continue
        candidate.compute_metrics.update(metrics)


def run_cli_tool(
    tool: ComputeTool,
    fasta_path: Path,
    workdir: Path,
    timeout: int,
) -> ToolRun:
    program = tool.address
    resolved = Path(program)
    if not resolved.is_file() and shutil.which(program) is None:
        return ToolRun(
            name=tool.name,
            kind="cli",
            status="skipped",
            detail=f"未找到可执行文件：{program}。已跳过，不填写结构指标。",
        )
    executable = str(resolved if resolved.is_file() else program)
    if tool.command.strip():
        rendered = (
            tool.command.replace("{program}", executable)
            .replace("{fasta}", str(fasta_path))
            .replace("{outdir}", str(workdir))
        )
        args = shlex.split(rendered)
    else:
        args = [executable, str(fasta_path), str(workdir)]
    try:
        completed = subprocess.run(
            args,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolRun(
            name=tool.name,
            kind="cli",
            status="failed",
            detail=f"调用失败：{exc}",
        )
    metrics: Dict[str, Dict[str, Any]] = {}
    result_file = workdir / "results.json"
    if result_file.is_file():
        try:
            metrics = parse_metrics(json.loads(result_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            metrics = {}
    if not metrics:
        metrics = parse_metrics(_load_json_text(completed.stdout) or {})
    tail = (completed.stderr or completed.stdout or "").strip()[-400:]
    if completed.returncode != 0:
        return ToolRun(
            name=tool.name,
            kind="cli",
            status="failed",
            detail=f"退出码 {completed.returncode}。{tail}",
            metrics_by_id=metrics,
        )
    if not metrics:
        return ToolRun(
            name=tool.name,
            kind="cli",
            status="failed",
            detail="程序已结束，但没有解析到 results.json 或标准输出中的指标。",
        )
    return ToolRun(
        name=tool.name,
        kind="cli",
        status="ok",
        detail=f"已回传 {len(metrics)} 条候选的计算指标。",
        metrics_by_id=metrics,
    )


def run_api_tool(
    tool: ComputeTool,
    candidates: List[Candidate],
    timeout: int,
) -> ToolRun:
    body = json.dumps(
        {"tool": tool.name, "sequences": _candidate_payload(candidates)},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if tool.token:
        headers["Authorization"] = f"Bearer {tool.token}"
    request = urllib.request.Request(tool.address, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ToolRun(
            name=tool.name,
            kind="api",
            status="failed",
            detail=f"接口调用失败：{exc}",
        )
    metrics = parse_metrics(_load_json_text(text) or {})
    if not metrics:
        return ToolRun(
            name=tool.name,
            kind="api",
            status="failed",
            detail="接口有响应，但没有解析到按候选编号索引的指标。",
        )
    return ToolRun(
        name=tool.name,
        kind="api",
        status="ok",
        detail=f"已回传 {len(metrics)} 条候选的计算指标。",
        metrics_by_id=metrics,
    )


def run_compute_tools(
    tools: List[ComputeTool],
    candidates: List[Candidate],
    fasta_path: Path,
    output_dir: Path,
    timeout: int,
) -> List[ToolRun]:
    runs: List[ToolRun] = []
    if not tools:
        runs.append(
            ToolRun(
                name="（未配置）",
                kind="none",
                status="skipped",
                detail="需求文件没有填写可用的本地程序或 API。本次只做序列规则分析。",
            )
        )
        return runs
    for index, tool in enumerate(tools, start=1):
        workdir = output_dir / f"tool_{index}_{tool.name}"
        workdir.mkdir(parents=True, exist_ok=True)
        if tool.kind == "cli":
            result = run_cli_tool(tool, fasta_path, workdir, timeout)
        else:
            result = run_api_tool(tool, candidates, timeout)
        if result.metrics_by_id:
            _apply(candidates, result.metrics_by_id)
        runs.append(result)
    return runs
