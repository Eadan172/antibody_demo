"""快筛打分。结构指标只在计算软件真实回传时参与，不补造数字。"""

from __future__ import annotations

from typing import List

from antibody_pipeline.models import Candidate
from antibody_pipeline.sequence_analysis import scan_ptm

HYDROPHOBIC = set("FWYILMV")


def _clamp(value: float, low: float = 1.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _as_score(value, default: float) -> float:
    try:
        return _clamp(float(value), 0.0, 10.0)
    except (TypeError, ValueError):
        return default


def screen_candidate(candidate: Candidate) -> Candidate:
    scan_ptm(candidate)
    cdr_hits = [hit for hit in candidate.ptm_hits if hit.in_cdr]
    gly = [hit for hit in cdr_hits if hit.kind == "N-糖基化"]
    deam = [hit for hit in cdr_hits if hit.kind == "脱酰胺"]
    ox = [hit for hit in cdr_hits if hit.kind == "氧化"]
    iso = [hit for hit in cdr_hits if hit.kind == "异构化"]

    developability = 9.0
    developability -= min(3, len(gly)) * 3
    developability -= min(4, len(deam)) * 1
    developability -= min(3, len(ox)) * 1
    developability -= min(3, len(iso)) * 1
    fmt = candidate.format or ""
    if "scFv" in fmt and "Fc" not in fmt:
        developability -= 1.0
    elif "scFv" in fmt:
        developability -= 0.5
    developability = _clamp(developability)

    structure = 8.0
    h3 = candidate.cdr_h3 or ""
    if h3:
        if len(h3) < 5 or len(h3) > 16:
            structure -= 2.0
        hydrophobic = sum(aa in HYDROPHOBIC for aa in h3) / len(h3)
        if hydrophobic > 0.45:
            structure -= 1.5
    else:
        structure -= 1.5
    germline = f"{candidate.vh_germline} {candidate.vl_germline}"
    if "IGHV2-70" in germline or "IGHV6-1" in germline:
        structure -= 0.5
        candidate.notes.append("胚系含 IGHV2-70 或 IGHV6-1，表达/免疫原性需额外关注")

    iptm = candidate.compute_metrics.get("iptm")
    if isinstance(iptm, (int, float)):
        if iptm >= 0.8:
            structure += 1.0
        elif iptm < 0.5:
            structure -= 1.0
    structure = _clamp(structure)

    function = _as_score(candidate.function_score, 6.0)
    specificity = _as_score(candidate.specificity_score, 6.0)

    if gly:
        status = "过滤"
        developability = min(developability, 2.0)
    elif developability <= 4 or len(cdr_hits) >= 5:
        status = "条件通过"
    else:
        status = "通过"

    candidate.screen_status = status
    candidate.scores = {
        "F": round(function, 1),
        "S": round(specificity, 1),
        "D": round(developability, 1),
        "St": round(structure, 1),
    }
    total = function + specificity + developability + structure
    candidate.composite = float(round(2.5 * total))
    return candidate


def screen_all(candidates: List[Candidate]) -> List[Candidate]:
    for candidate in candidates:
        screen_candidate(candidate)
    return candidates
