"""串联要求分析、调研、设计、计算、快筛和报告。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from antibody_pipeline.compute_runner import run_compute_tools
from antibody_pipeline.dedup import build_dedup
from antibody_pipeline.demo_data import build_demo
from antibody_pipeline.envfile import load_env_file
from antibody_pipeline.render import render_fasta, write_reports
from antibody_pipeline.scoring import screen_all
from antibody_pipeline.state import checkpoint_ready, load_checkpoint, save_checkpoint


def load_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    config_path: Path,
    demo: bool = False,
    resume: bool = False,
    n_override: Optional[int] = None,
    base_url: str = "",
    model: str = "",
    project_root: Optional[Path] = None,
) -> Path:
    root = project_root or Path.cwd()
    load_env_file(root / ".env")
    config = load_config(config_path)
    pipeline_cfg = config.get("pipeline") or {}
    compute_cfg = config.get("compute") or {}
    routes = pipeline_cfg.get("routes") or [
        {"id": "boltz", "prefix": "BLZ", "expert": "博兹", "title": "Boltz·MSA"},
        {"id": "protenix", "prefix": "PRX", "expert": "普腾", "title": "Protenix·MSA"},
    ]
    default_n = int(pipeline_cfg.get("default_n_per_route_per_target") or 6)
    batch_size = int(pipeline_cfg.get("design_batch_size") or 3)
    timeout = int(compute_cfg.get("timeout_seconds") or 3600)

    output_dir.mkdir(parents=True, exist_ok=True)
    phases: List[str] = []

    def log(message: str) -> None:
        print(message, flush=True)
        phases.append(message)

    state_dir = output_dir / "_state"
    source_note = ""

    if demo:
        log("阶段：离线演示。不调用大模型，用内置占位靶点和序列写出全套文件。")
        n_demo = n_override or 2
        spec, pack, candidates, route_notes, strategies = build_demo(n_demo)
        source_note = "本目录由 --demo 生成，序列和靶点档案都是占位数据，不能当设计结论。"
        text = input_path.read_text(encoding="utf-8") if input_path.is_file() else ""
        if text.strip():
            from antibody_pipeline.parse_input import parse_requirement_hints

            hints = parse_requirement_hints(text, default_n)
            if hints["compute_tools"]:
                spec.compute_tools = hints["compute_tools"]
                log(f"演示仍会尝试需求文件里的 {len(spec.compute_tools)} 个计算软件。")
        save_checkpoint(state_dir, spec, pack, candidates, route_notes, strategies)
    elif resume and checkpoint_ready(state_dir):
        log("阶段：从已有检查点继续，跳过要求分析、调研和序列设计。")
        spec, pack, candidates, route_notes, strategies = load_checkpoint(state_dir)
        source_note = "序列来自大模型设计或上一次运行的检查点；指标以本次序列规则和计算回传为准。"
    else:
        text = input_path.read_text(encoding="utf-8")
        client = _make_client(config, base_url, model)
        from antibody_pipeline.stages import analyze_requirements, design_all, research_targets

        spec = analyze_requirements(client, text, default_n, log)
        if n_override:
            spec.n_per_route_per_target = n_override
            log(f"命令行把每路线每靶点候选数改为 {n_override}。")
        pack = research_targets(client, spec, log)
        candidates, route_notes, strategies = design_all(
            client, spec, pack.selected, routes, batch_size, log
        )
        source_note = "序列由大模型按需求生成，尚未经过结构软件或湿实验确认。"
        save_checkpoint(state_dir, spec, pack, candidates, route_notes, strategies)
        if not candidates:
            log("没有得到通过序列检查的候选，仍会写出说明性报告。")

    log("阶段：计算。按需求文件调用本地程序或 API；没有配置或调用失败时只保留序列规则。")
    fasta_path = output_dir / "_input_for_compute.fasta"
    fasta_path.write_text(render_fasta(candidates, datetime.now().strftime("%Y-%m-%d %H:%M"), "ALL"), encoding="utf-8")
    tools = run_compute_tools(
        spec.compute_tools,
        candidates,
        fasta_path,
        output_dir / "_compute",
        timeout,
    )
    for run in tools:
        log(f"计算 {run.name}：{run.status}。{run.detail}")

    log("阶段：去冗余。比较两条路线的 VH、VL 和 CDR-H3，表位不同的配对只标注、不合并。")
    dedup = build_dedup(candidates)
    log("阶段：快筛。用序列规则复核 PTM、过滤 CDR 糖基化并打分。")
    screen_all(candidates)
    log("阶段：报告汇编。写入调研、设计、FASTA、去冗余、汇总、快筛、综合评估和日志。")
    written = write_reports(
        output_dir,
        spec,
        pack,
        candidates,
        dedup,
        tools,
        route_notes,
        strategies,
        phases,
        source_note,
    )
    latest = root / "output" / "LATEST.txt"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(str(output_dir.resolve()) + "\n", encoding="utf-8")
    log(f"完成。共 {len(written)} 个交付文件，目录：{output_dir}")
    return output_dir


def _make_client(config: dict, base_url: str, model: str):
    import os

    from antibody_pipeline.llm_client import LLMClient

    llm_cfg = config.get("llm") or {}
    return LLMClient(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=base_url or os.environ.get("LLM_BASE_URL") or llm_cfg.get("base_url") or "https://api.openai.com/v1",
        model=model or os.environ.get("LLM_MODEL") or llm_cfg.get("model") or "gpt-4o-mini",
        temperature=float(llm_cfg.get("temperature") or 0.4),
        timeout=int(llm_cfg.get("timeout_seconds") or 180),
        max_tokens=int(llm_cfg.get("max_tokens") or 12000),
    )
