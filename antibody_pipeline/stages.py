"""要求分析、靶点调研、按本次路线分批设计。"""

from __future__ import annotations

from typing import Callable, Dict, List, Sequence

from antibody_pipeline.models import Candidate, RequirementSpec, ResearchPack, TargetDossier
from antibody_pipeline.parse_input import parse_requirement_hints, slug_target
from antibody_pipeline.prompts import DESIGN_USER, RESEARCH_USER, SPEC_USER, SYSTEM
from antibody_pipeline.sequence_analysis import chain_problem, clean_sequence

LogFn = Callable[[str], None]


def _lines(text: str) -> List[str]:
    items = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-").strip()
        if line:
            items.append(line)
    return items


def build_spec_from_hints(text: str, default_n: int, hints: dict | None = None) -> RequirementSpec:
    """在没有模型时，用需求文件里的明确字段做一版规格。"""
    hints = hints or parse_requirement_hints(text, default_n)
    targets = hints["targets"]
    return RequirementSpec(
        project_name=hints["project_name"],
        task_summary=hints["task_text"] or "按输入文件完成抗体候选设计与评估。",
        target_mode="specified" if targets else "discover",
        target_names=targets,
        n_targets=len(targets) if targets else 3,
        species=_lines(hints["species_text"]) or ["见需求原文"],
        physicochemical=_lines(hints["physicochemical_text"]) or ["见需求原文"],
        formats=_lines(hints["formats_text"]) or ["IgG1", "IgG4", "scFv", "Fab"],
        modalities=_lines(hints["modalities_text"]) or ["见需求原文"],
        n_per_route_per_target=hints["n_per_route_per_target"],
        extra_constraints="",
        raw_text=text,
        compute_tools=list(hints["compute_tools"]),
    )


def analyze_requirements(client, text: str, default_n: int, log: LogFn) -> RequirementSpec:
    hints = parse_requirement_hints(text, default_n)
    log("阶段：要求分析。先读取输入文件中的靶点、数量和计算软件，再请模型整理其余要求。")
    data = client.chat_json(
        SYSTEM,
        SPEC_USER.format(
            text=text,
            project=hints["project_name"],
            targets="、".join(hints["targets"]) or "（未指定）",
            count=hints["n_per_route_per_target"],
            tool_count=len(hints["compute_tools"]),
        ),
        temperature=0.1,
    )
    base = build_spec_from_hints(text, default_n, hints)
    if isinstance(data, dict):
        base.task_summary = str(data.get("task_summary") or base.task_summary)
        base.species = _as_list(data.get("species")) or base.species
        base.physicochemical = _as_list(data.get("physicochemical")) or base.physicochemical
        base.formats = _as_list(data.get("formats")) or base.formats
        base.modalities = _as_list(data.get("modalities")) or base.modalities
        base.extra_constraints = str(data.get("extra_constraints") or "")
        if not hints["targets"]:
            names = _as_list(data.get("target_names"))
            mode = str(data.get("target_mode") or "discover")
            base.target_mode = "specified" if mode == "specified" and names else "discover"
            base.target_names = names if base.target_mode == "specified" else []
            try:
                base.n_targets = int(data.get("n_targets") or base.n_targets)
            except (TypeError, ValueError):
                pass
    # 文件里写死的数量、靶点和软件地址覆盖模型输出
    if hints["targets"]:
        base.target_mode = "specified"
        base.target_names = hints["targets"]
        base.n_targets = len(hints["targets"])
    base.n_per_route_per_target = hints["n_per_route_per_target"]
    base.compute_tools = list(hints["compute_tools"])
    log(
        f"要求已拆解：模式={base.target_mode}，靶点={base.target_names or '待调研'}，"
        f"每路线每靶点 {base.n_per_route_per_target} 条，计算软件 {len(base.compute_tools)} 个。"
    )
    return base


def _as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def _dossier_from(item: dict) -> TargetDossier:
    name = str(item.get("name") or "").strip() or "未命名靶点"
    dossier = TargetDossier(
        name=name,
        aliases=str(item.get("aliases") or ""),
        uniprot=str(item.get("uniprot") or ""),
        mol_type=str(item.get("mol_type") or ""),
        expression=str(item.get("expression") or ""),
        approved_drugs=str(item.get("approved_drugs") or ""),
        pipeline=str(item.get("pipeline") or ""),
        design_points=str(item.get("design_points") or ""),
        differentiation=str(item.get("differentiation") or ""),
        risks=str(item.get("risks") or ""),
        heat=str(item.get("heat") or ""),
        competition=str(item.get("competition") or ""),
        slug=slug_target(name),
    )
    return dossier


def research_targets(client, spec: RequirementSpec, log: LogFn) -> ResearchPack:
    log("阶段：靶点调研。按需求筛选或核对靶点，并整理设计要点。")
    data = client.chat_json(
        SYSTEM,
        RESEARCH_USER.format(
            summary=spec.task_summary,
            mode=spec.target_mode,
            targets="、".join(spec.target_names) or "（无，需筛选）",
            n_targets=spec.n_targets,
            species="；".join(spec.species),
            physicochemical="；".join(spec.physicochemical),
            modalities="；".join(spec.modalities),
            extra=spec.extra_constraints or "无",
        ),
        temperature=0.2,
    )
    if not isinstance(data, dict):
        raise RuntimeError("靶点调研没有返回对象")
    selected = []
    for item in data.get("selected") or []:
        if isinstance(item, dict) and item.get("name"):
            selected.append(_dossier_from(item))
    if spec.target_mode == "specified":
        by_slug = {item.slug: item for item in selected}
        ordered = []
        for name in spec.target_names:
            slug = slug_target(name)
            if slug in by_slug:
                ordered.append(by_slug[slug])
            else:
                ordered.append(
                    TargetDossier(
                        name=name.split("（")[0].split("(")[0].strip(),
                        aliases=name,
                        pipeline="模型未返回该靶点档案，需复核",
                        slug=slug,
                    )
                )
        selected = ordered
    elif not selected:
        raise RuntimeError("调研没有选出靶点")
    else:
        selected = selected[: max(1, spec.n_targets)]
    pool = []
    for item in data.get("pool") or []:
        if isinstance(item, dict):
            pool.append({key: str(item.get(key) or "") for key in ("name", "heat", "approved", "competition", "decision", "reason")})
    pack = ResearchPack(
        method=str(data.get("method") or ""),
        criteria=_as_list(data.get("criteria")),
        pool=pool,
        selected=selected,
        conclusion=str(data.get("conclusion") or ""),
    )
    log("调研完成：" + "、".join(item.name for item in pack.selected))
    return pack


def _route_name(route: dict) -> str:
    return str(route.get("name") or route.get("expert") or route.get("title") or "设计路线")


def _focus(route: dict) -> str:
    text = str(route.get("focus") or "").strip()
    if text:
        return text
    return "按用户需求做互补设计。不要把候选说成用户未指定的软件或商品输出。"


def _normalize_candidate(raw: dict, route: dict, target: TargetDossier, index: int) -> Candidate:
    prefix = route["prefix"]
    name = _route_name(route)
    candidate = Candidate(
        id=f"{prefix}-{target.slug}-{index:02d}",
        route=str(route.get("title") or name),
        route_label=route["prefix"],
        expert=name,
        target=target.name,
        epitope=str(raw.get("epitope") or ""),
        format=str(raw.get("format") or ""),
        vh_germline=str(raw.get("vh_germline") or ""),
        vl_germline=str(raw.get("vl_germline") or ""),
        vh=clean_sequence(str(raw.get("vh") or "")),
        vl=clean_sequence(str(raw.get("vl") or "")),
        cdr_h1=clean_sequence(str(raw.get("cdr_h1") or "")),
        cdr_h2=clean_sequence(str(raw.get("cdr_h2") or "")),
        cdr_h3=clean_sequence(str(raw.get("cdr_h3") or "")),
        cdr_l1=clean_sequence(str(raw.get("cdr_l1") or "")),
        cdr_l2=clean_sequence(str(raw.get("cdr_l2") or "")),
        cdr_l3=clean_sequence(str(raw.get("cdr_l3") or "")),
        kd_pred=str(raw.get("kd_pred") or "预测区间未给出"),
        specificity=str(raw.get("specificity") or ""),
        immunogenicity=str(raw.get("immunogenicity") or ""),
        aggregation=str(raw.get("aggregation") or ""),
        tm=str(raw.get("tm") or ""),
        ptm_note=str(raw.get("ptm_note") or ""),
        strategy=str(raw.get("strategy") or ""),
        optimization=str(raw.get("optimization") or ""),
        function_score=_score(raw.get("function_score")),
        specificity_score=_score(raw.get("specificity_score")),
        source="llm",
    )
    return candidate


def _score(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 6.0


def _problems(candidate: Candidate) -> List[str]:
    issues = []
    vh_issue = chain_problem(candidate.vh, "VH")
    vl_issue = chain_problem(candidate.vl, "VL")
    if vh_issue:
        issues.append(vh_issue)
    if vl_issue:
        issues.append(vl_issue)
    for name, field, chain in (
        ("H1", "cdr_h1", "vh"),
        ("H2", "cdr_h2", "vh"),
        ("H3", "cdr_h3", "vh"),
        ("L1", "cdr_l1", "vl"),
        ("L2", "cdr_l2", "vl"),
        ("L3", "cdr_l3", "vl"),
    ):
        motif = getattr(candidate, field)
        if motif and motif not in getattr(candidate, chain):
            issues.append(f"CDR-{name} 不是对应链的子串")
    if not candidate.cdr_h3:
        issues.append("缺少 CDR-H3")
    return issues


def design_one_batch(client, spec: RequirementSpec, route: dict, target: TargetDossier, batch: int, used_h3: Sequence[str], used_vh: Sequence[str], log: LogFn):
    dossier = (
        f"名称：{target.name}\n别名：{target.aliases}\nUniProt：{target.uniprot}\n"
        f"类型：{target.mol_type}\n表达：{target.expression}\n上市药：{target.approved_drugs}\n"
        f"在研：{target.pipeline}\n设计要点：{target.design_points}\n风险：{target.risks}"
    )
    data = client.chat_json(
        SYSTEM,
        DESIGN_USER.format(
            name=_route_name(route),
            batch=batch,
            dossier=dossier,
            species="；".join(spec.species),
            physicochemical="；".join(spec.physicochemical),
            formats="；".join(spec.formats),
            modalities="；".join(spec.modalities),
            extra=spec.extra_constraints or "无",
            focus=_focus(route),
            used_h3="、".join(used_h3) or "无",
            used_vh="、".join(used_vh) or "无",
        ),
        temperature=0.5,
    )
    overview = ""
    strategy = ""
    rows = []
    if isinstance(data, dict):
        overview = str(data.get("route_overview") or "")
        strategy = str(data.get("target_strategy") or "")
        rows = [row for row in data.get("candidates") or [] if isinstance(row, dict)]
    accepted: List[Candidate] = []
    for row in rows:
        candidate = _normalize_candidate(raw=row, route=route, target=target, index=1)
        issues = _problems(candidate)
        if issues:
            log(f"{_route_name(route)} / {target.name} 有一条未通过序列检查：{'；'.join(issues)}")
            continue
        if candidate.cdr_h3 in used_h3:
            log(f"{_route_name(route)} / {target.name} 的 CDR-H3 与已有候选重复，已丢弃一条。")
            continue
        if not candidate.strategy:
            candidate.strategy = strategy
        accepted.append(candidate)
    return accepted, overview, strategy


def design_all(client, spec: RequirementSpec, targets: List[TargetDossier], routes: List[dict], batch_size: int, log: LogFn):
    names = "、".join(_route_name(route) for route in routes) or "未配置路线"
    log(f"阶段：分路线设计。本次路线为 {names}。这些名称来自需求或配置，只表示互补策略，不代表特定软件。")
    notes: Dict[str, str] = {}
    strategies: Dict[str, str] = {}
    candidates: List[Candidate] = []
    used_h3: List[str] = []
    used_vh: List[str] = []
    counters = {(route["id"], target.slug): 0 for route in routes for target in targets}

    for target in targets:
        for route in routes:
            need = spec.n_per_route_per_target
            log(f"设计 {_route_name(route)} × {target.name}，目标 {need} 条。")
            guard = 0
            while counters[(route["id"], target.slug)] < need and guard < need + 2:
                guard += 1
                batch = min(batch_size, need - counters[(route["id"], target.slug)])
                fresh, overview, strategy = design_one_batch(
                    client, spec, route, target, batch, used_h3, used_vh, log
                )
                if overview and route["id"] not in notes:
                    notes[route["id"]] = overview
                if strategy:
                    strategies[f"{route['id']}:{target.slug}"] = strategy
                if not fresh:
                    log(f"{_route_name(route)} × {target.name} 本批没有合格序列，停止补齐。")
                    break
                for candidate in fresh:
                    counters[(route["id"], target.slug)] += 1
                    if counters[(route["id"], target.slug)] > need:
                        break
                    candidate.id = (
                        f"{route['prefix']}-{target.slug}-"
                        f"{counters[(route['id'], target.slug)]:02d}"
                    )
                    candidates.append(candidate)
                    used_h3.append(candidate.cdr_h3)
                    if candidate.vh_germline:
                        used_vh.append(candidate.vh_germline)
            got = counters[(route["id"], target.slug)]
            log(f"{_route_name(route)} × {target.name} 得到 {got}/{need} 条。")
    return candidates, notes, strategies
