"""序列规则分析：氨基酸校验、CDR 定位、翻译后修饰位点扫描。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from antibody_pipeline.models import Candidate, PTMHit

AA = set("ACDEFGHIKLMNPQRSTVWY")

_MOTIFS = (
    ("N-糖基化", re.compile(r"N(?!P)[A-Z][ST]")),
    ("脱酰胺", re.compile(r"N[GSN]")),
    ("氧化", re.compile(r"M")),
    ("异构化", re.compile(r"D[GS]")),
)

_CDR_FIELDS = (
    ("H1", "cdr_h1", "VH"),
    ("H2", "cdr_h2", "VH"),
    ("H3", "cdr_h3", "VH"),
    ("L1", "cdr_l1", "VL"),
    ("L2", "cdr_l2", "VL"),
    ("L3", "cdr_l3", "VL"),
)


def clean_sequence(seq: str) -> str:
    return re.sub(r"[^A-Za-z]", "", seq or "").upper()


def chain_problem(seq: str, kind: str) -> str:
    if not seq:
        return f"{kind} 为空"
    bad = sorted({ch for ch in seq if ch not in AA})
    if bad:
        return f"{kind} 含非标准氨基酸 {''.join(bad)}"
    low, high = (100, 150) if kind == "VH" else (95, 140)
    if not (low <= len(seq) <= high):
        return f"{kind} 长度 {len(seq)} 不在可变区常见范围 {low}-{high}"
    return ""


def _find_span(seq: str, motif: str) -> Optional[Tuple[int, int]]:
    motif = clean_sequence(motif)
    if len(motif) < 2:
        return None
    index = seq.find(motif)
    if index < 0:
        return None
    return index + 1, index + len(motif)  # 1-based inclusive


def _heuristic_h3(vh: str) -> str:
    match = re.search(r"C([A-Z]{3,35}?)WG[QKRG]", vh)
    return match.group(1) if match else ""


def _heuristic_l3(vl: str) -> str:
    match = re.search(r"C([A-Z]{3,25}?)FG[A-Z]G", vl)
    return match.group(1) if match else ""


def locate_cdrs(candidate: Candidate) -> None:
    """把 CDR 字符串对齐到 VH/VL。对不上时用保守半胱氨酸启发式补 H3/L3。"""
    if not candidate.cdr_h3:
        candidate.cdr_h3 = _heuristic_h3(candidate.vh)
        if candidate.cdr_h3:
            candidate.notes.append("CDR-H3 由序列启发式补全（C…WGXG）")
    if not candidate.cdr_l3:
        candidate.cdr_l3 = _heuristic_l3(candidate.vl)
        if candidate.cdr_l3:
            candidate.notes.append("CDR-L3 由序列启发式补全（C…FGXG）")

    spans: Dict[str, Optional[tuple]] = {}
    for name, field, chain in _CDR_FIELDS:
        motif = getattr(candidate, field)
        seq = candidate.vh if chain == "VH" else candidate.vl
        span = _find_span(seq, motif)
        if motif and span is None:
            if name == "H3":
                guessed = _heuristic_h3(candidate.vh)
                if guessed:
                    candidate.cdr_h3 = guessed
                    span = _find_span(candidate.vh, guessed)
                    candidate.notes.append("原 CDR-H3 不在 VH 中，已改用启发式片段")
            elif name == "L3":
                guessed = _heuristic_l3(candidate.vl)
                if guessed:
                    candidate.cdr_l3 = guessed
                    span = _find_span(candidate.vl, guessed)
                    candidate.notes.append("原 CDR-L3 不在 VL 中，已改用启发式片段")
            if span is None:
                candidate.notes.append(f"CDR-{name} 注释与序列不一致，PTM 不把该注释当 CDR")
        spans[name] = span
    candidate.cdr_spans = spans


def _in_cdr(position: int, length: int, chain: str, spans: Dict[str, Optional[tuple]]) -> str:
    names = ("H1", "H2", "H3") if chain == "VH" else ("L1", "L2", "L3")
    for name in names:
        span = spans.get(name)
        if not span:
            continue
        start, end = span
        motif_end = position + length - 1
        if position <= end and motif_end >= start:
            return name
    return ""


def scan_ptm(candidate: Candidate) -> List[PTMHit]:
    locate_cdrs(candidate)
    hits: List[PTMHit] = []
    for chain, seq in (("VH", candidate.vh), ("VL", candidate.vl)):
        for kind, pattern in _MOTIFS:
            for match in pattern.finditer(seq):
                cdr = _in_cdr(match.start() + 1, len(match.group(0)), chain, candidate.cdr_spans)
                hits.append(
                    PTMHit(
                        kind=kind,
                        motif=match.group(0),
                        position=match.start() + 1,
                        chain=chain,
                        in_cdr=bool(cdr),
                        cdr_name=cdr,
                    )
                )
    candidate.ptm_hits = hits
    return hits


def germline_token(label: str) -> str:
    match = re.search(r"IG[HKL]V\d+-\d+", label or "", flags=re.I)
    if not match:
        return label.strip() or "未标注"
    token = match.group(0).upper()
    token = token.replace("IGKV", "IGKV").replace("IGLV", "IGLV").replace("IGHV", "IGHV")
    return token


def format_hits(hits: List[PTMHit], only_cdr: bool = False) -> str:
    chosen = [hit for hit in hits if hit.in_cdr] if only_cdr else hits
    if not chosen:
        return "未检出" if only_cdr else "未检出规则位点"
    parts = []
    for hit in chosen:
        where = f"CDR-{hit.cdr_name}" if hit.in_cdr else "框架"
        parts.append(f"{hit.chain}{hit.position}{hit.motif}（{hit.kind}，{where}）")
    return "；".join(parts)
