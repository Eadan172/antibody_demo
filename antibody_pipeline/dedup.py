"""双路线序列去冗余。比较的是本次实际生成的序列，不引用外部名单。"""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, List

from antibody_pipeline.models import Candidate, DedupReport
from antibody_pipeline.sequence_analysis import germline_token


def _ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _epitope_key(text: str) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def build_dedup(candidates: List[Candidate]) -> DedupReport:
    exact = []
    seen_vh: Dict[str, str] = {}
    seen_vl: Dict[str, str] = {}
    for candidate in candidates:
        if candidate.vh in seen_vh:
            exact.append(f"VH 完全一致：{seen_vh[candidate.vh]} 与 {candidate.id}")
        else:
            seen_vh[candidate.vh] = candidate.id
        if candidate.vl in seen_vl:
            exact.append(f"VL 完全一致：{seen_vl[candidate.vl]} 与 {candidate.id}")
        else:
            seen_vl[candidate.vl] = candidate.id

    h3_map: Dict[str, List[str]] = defaultdict(list)
    for candidate in candidates:
        if candidate.cdr_h3:
            h3_map[candidate.cdr_h3].append(candidate.id)
    collisions = [
        f"{seq} ← {', '.join(ids)}"
        for seq, ids in h3_map.items()
        if len(ids) > 1
    ]

    groups = []
    for i, left in enumerate(candidates):
        for right in candidates[i + 1 :]:
            if left.route_label == right.route_label:
                continue
            vl_ratio = _ratio(left.vl, right.vl)
            vh_ratio = _ratio(left.vh, right.vh)
            same_l3 = bool(left.cdr_l3) and left.cdr_l3 == right.cdr_l3
            # 同一人源框架会让整条 VH 相似度很高，但 CDR 不同就不算需要合并。
            # 只记录轻链几乎相同，或 CDR-L3 相同且轻链仍然很接近的配对。
            if vl_ratio < 0.97 and not (same_l3 and vl_ratio >= 0.90):
                continue
            same_epitope = _epitope_key(left.epitope) == _epitope_key(right.epitope)
            groups.append(
                {
                    "left": left.id,
                    "right": right.id,
                    "vl_identity": round(vl_ratio, 3),
                    "vh_identity": round(vh_ratio, 3),
                    "same_epitope": same_epitope,
                    "advice": "可合并评估" if same_epitope else "表位不同，不合并，只标注框架趋同",
                }
            )

    def distribution(attr: str) -> List[Dict[str, str]]:
        table: Dict[str, List[str]] = defaultdict(list)
        for candidate in candidates:
            token = germline_token(getattr(candidate, attr))
            table[token].append(f"{candidate.id}")
        rows = []
        for token in sorted(table):
            rows.append({"germline": token, "candidates": "、".join(table[token])})
        return rows

    lines = []
    if exact:
        lines.append(f"发现 {len(exact)} 处 VH 或 VL 完全重复，快筛时应避免把它们当成独立候选。")
    else:
        lines.append("没有 VH 或 VL 完全相同的意外重复。")
    if collisions:
        lines.append(f"CDR-H3 有 {len(collisions)} 组重复，多样性不足。")
    else:
        lines.append("已标注的 CDR-H3 全部不同。")
    if groups:
        lines.append(f"有 {len(groups)} 对跨路线轻链高度接近（一致度 ≥ 0.97，或 CDR-L3 相同且一致度 ≥ 0.90）。同一路线里只在「完全重复」中列出整链相同的情况。")
    else:
        lines.append("没有轻链高度接近的配对。同一重链框架但 CDR-H3 不同，不视为重复。")

    return DedupReport(
        exact_duplicates=exact,
        h3_unique=not collisions,
        h3_collisions=collisions,
        groups=groups,
        vh_table=distribution("vh_germline"),
        vl_table=distribution("vl_germline"),
        summary_lines=lines,
    )
