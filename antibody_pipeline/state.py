"""把大模型阶段的结果写到输出目录，便于中断后继续。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from antibody_pipeline.models import (
    Candidate,
    ComputeTool,
    RequirementSpec,
    ResearchPack,
    TargetDossier,
)


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(state_dir: Path, spec: RequirementSpec, pack: ResearchPack, candidates: List[Candidate], route_notes: Dict[str, str], strategies: Dict[str, str]) -> None:
    tools = [
        {
            "name": tool.name,
            "kind": tool.kind,
            "address": tool.address,
            "command": tool.command,
            "token": tool.token,
        }
        for tool in spec.compute_tools
    ]
    _dump(state_dir / "spec.json", {**spec.to_dict(), "raw_text": spec.raw_text, "compute_tools": tools})
    _dump(state_dir / "research.json", pack.to_dict())
    _dump(
        state_dir / "design.json",
        {
            "candidates": [item.to_dict() for item in candidates],
            "route_notes": route_notes,
            "strategies": strategies,
        },
    )


def checkpoint_ready(state_dir: Path) -> bool:
    return all((state_dir / name).is_file() for name in ("spec.json", "research.json", "design.json"))


def load_checkpoint(state_dir: Path) -> Tuple[RequirementSpec, ResearchPack, List[Candidate], Dict[str, str], Dict[str, str]]:
    spec_raw = _load(state_dir / "spec.json")
    research_raw = _load(state_dir / "research.json")
    design_raw = _load(state_dir / "design.json")
    tools = [
        ComputeTool(
            name=item["name"],
            kind=item["kind"],
            address=item["address"],
            command=item.get("command") or "",
            token=item.get("token") or "",
        )
        for item in spec_raw.get("compute_tools") or []
        if item.get("address")
    ]
    spec = RequirementSpec(
        project_name=spec_raw["project_name"],
        task_summary=spec_raw["task_summary"],
        target_mode=spec_raw["target_mode"],
        target_names=list(spec_raw.get("target_names") or []),
        n_targets=int(spec_raw.get("n_targets") or 1),
        species=list(spec_raw.get("species") or []),
        physicochemical=list(spec_raw.get("physicochemical") or []),
        formats=list(spec_raw.get("formats") or []),
        modalities=list(spec_raw.get("modalities") or []),
        n_per_route_per_target=int(spec_raw.get("n_per_route_per_target") or 1),
        extra_constraints=spec_raw.get("extra_constraints") or "",
        raw_text=spec_raw.get("raw_text") or "",
        compute_tools=tools,
    )
    selected = [TargetDossier(**item) for item in research_raw.get("selected") or []]
    pack = ResearchPack(
        method=research_raw.get("method") or "",
        criteria=list(research_raw.get("criteria") or []),
        pool=list(research_raw.get("pool") or []),
        selected=selected,
        conclusion=research_raw.get("conclusion") or "",
    )
    candidates = []
    for item in design_raw.get("candidates") or []:
        item = dict(item)
        item["ptm_hits"] = []
        item["cdr_spans"] = {}
        item["notes"] = list(item.get("notes") or [])
        item["scores"] = {}
        item["compute_metrics"] = dict(item.get("compute_metrics") or {})
        item["screen_status"] = ""
        item["composite"] = 0
        candidates.append(Candidate(**item))
    return (
        spec,
        pack,
        candidates,
        dict(design_raw.get("route_notes") or {}),
        {str(key): value for key, value in (design_raw.get("strategies") or {}).items()},
    )
