"""流水线数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ComputeTool:
    name: str
    kind: str  # cli | api
    address: str
    command: str = ""
    token: str = ""


@dataclass
class RequirementSpec:
    project_name: str
    task_summary: str
    target_mode: str  # specified | discover
    target_names: List[str]
    n_targets: int
    species: List[str]
    physicochemical: List[str]
    formats: List[str]
    modalities: List[str]
    n_per_route_per_target: int
    extra_constraints: str
    raw_text: str
    compute_tools: List[ComputeTool] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "project_name": self.project_name,
            "task_summary": self.task_summary,
            "target_mode": self.target_mode,
            "target_names": list(self.target_names),
            "n_targets": self.n_targets,
            "species": list(self.species),
            "physicochemical": list(self.physicochemical),
            "formats": list(self.formats),
            "modalities": list(self.modalities),
            "n_per_route_per_target": self.n_per_route_per_target,
            "extra_constraints": self.extra_constraints,
            "compute_tools": [
                {
                    "name": t.name,
                    "kind": t.kind,
                    "address": t.address,
                    "command": t.command,
                    "token": "***" if t.token else "",
                }
                for t in self.compute_tools
            ],
        }
        return data


@dataclass
class TargetDossier:
    name: str
    aliases: str = ""
    uniprot: str = ""
    mol_type: str = ""
    expression: str = ""
    approved_drugs: str = ""
    pipeline: str = ""
    design_points: str = ""
    differentiation: str = ""
    risks: str = ""
    heat: str = ""
    competition: str = ""
    slug: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ResearchPack:
    method: str
    criteria: List[str]
    pool: List[Dict[str, str]]
    selected: List[TargetDossier]
    conclusion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "criteria": self.criteria,
            "pool": self.pool,
            "selected": [t.to_dict() for t in self.selected],
            "conclusion": self.conclusion,
        }


@dataclass
class PTMHit:
    kind: str
    motif: str
    position: int  # 1-based
    chain: str  # VH | VL
    in_cdr: bool
    cdr_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Candidate:
    id: str
    route: str
    route_label: str
    expert: str
    target: str
    epitope: str
    format: str
    vh_germline: str
    vl_germline: str
    vh: str
    vl: str
    cdr_h1: str = ""
    cdr_h2: str = ""
    cdr_h3: str = ""
    cdr_l1: str = ""
    cdr_l2: str = ""
    cdr_l3: str = ""
    kd_pred: str = ""
    specificity: str = ""
    immunogenicity: str = ""
    aggregation: str = ""
    tm: str = ""
    ptm_note: str = ""
    strategy: str = ""
    optimization: str = ""
    function_score: float = 6.0
    specificity_score: float = 6.0
    source: str = "llm"
    ptm_hits: List[PTMHit] = field(default_factory=list)
    cdr_spans: Dict[str, Optional[tuple]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    screen_status: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    compute_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data["ptm_hits"] = [h.to_dict() for h in self.ptm_hits]
        spans = {}
        for key, val in self.cdr_spans.items():
            spans[key] = list(val) if val else None
        data["cdr_spans"] = spans
        return data


@dataclass
class ToolRun:
    name: str
    kind: str
    status: str  # ok | skipped | failed
    detail: str
    metrics_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "detail": self.detail,
            "metrics_by_id": self.metrics_by_id,
        }


@dataclass
class DedupReport:
    exact_duplicates: List[str]
    h3_unique: bool
    h3_collisions: List[str]
    groups: List[Dict[str, Any]]
    vh_table: List[Dict[str, str]]
    vl_table: List[Dict[str, str]]
    summary_lines: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()
