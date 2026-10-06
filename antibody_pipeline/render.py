"""把结构化结果写成与专家团流程对应的交付文件。"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from antibody_pipeline.models import (
    Candidate,
    DedupReport,
    RequirementSpec,
    ResearchPack,
    TargetDossier,
    ToolRun,
)
from antibody_pipeline.sequence_analysis import format_hits, germline_token


def _md(text: str) -> str:
    return (text or "").strip() or "未提供"


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    split = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |" for row in rows]
    return "\n".join([head, split, *body]) if rows else "\n".join([head, split, "| " + " | ".join("—" for _ in headers) + " |"])


def _by_target(candidates: Iterable[Candidate]) -> Dict[str, List[Candidate]]:
    grouped: Dict[str, List[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.target].append(candidate)
    for group in grouped.values():
        group.sort(key=lambda item: item.composite, reverse=True)
    return grouped


def _score_text(candidate: Candidate) -> str:
    scores = candidate.scores or {}
    return f"{scores.get('F', '—')}/{scores.get('S', '—')}/{scores.get('D', '—')}/{scores.get('St', '—')}"


def render_research(pack: ResearchPack, spec: RequirementSpec, stamp: str) -> str:
    pool_rows = [
        [item.get("name", ""), item.get("heat", ""), item.get("approved", ""), item.get("competition", ""), item.get("decision", ""), item.get("reason", "")]
        for item in pack.pool
    ]
    parts = [
        f"# 靶点调研报告",
        "",
        f"> 项目：{spec.project_name}  ",
        f"> 生成时间：{stamp}  ",
        "> 说明：内容来自需求拆解后的公开信息整理，不确定的管线与编号已要求标注为需复核，不构成竞品数据库的实时结果。",
        "",
        "## 一、调研方法",
        "",
        _md(pack.method),
        "",
        "筛选时对照的要求：",
        "",
    ]
    for index, item in enumerate(pack.criteria or ["研究热度", "上市药物数量", "结构是否够用于抗体设计", "是否还有差异化空间"], start=1):
        parts.append(f"{index}. {item}")
    parts.extend(["", "## 二、靶点候选池与筛选过程", "", _table(
        ["候选靶点", "研究热度", "上市药物", "竞争密度", "筛选结论", "理由"],
        pool_rows,
    ), "", "## 三、进入设计的靶点", ""])
    for index, target in enumerate(pack.selected, start=1):
        parts.extend([
            f"### 靶点 {index}：{target.name}",
            "",
            f"- **别名**：{_md(target.aliases)}",
            f"- **UniProt**：{_md(target.uniprot)}",
            f"- **类型**：{_md(target.mol_type)}",
            f"- **表达谱**：{_md(target.expression)}",
            f"- **上市药物**：{_md(target.approved_drugs)}",
            f"- **在研格局**：{_md(target.pipeline)}",
            f"- **热度**：{_md(target.heat)}",
            f"- **竞争**：{_md(target.competition)}",
            f"- **设计要点**：{_md(target.design_points)}",
            f"- **差异化**：{_md(target.differentiation)}",
            f"- **主要风险**：{_md(target.risks)}",
            "",
        ])
    names = "、".join(item.name for item in pack.selected)
    parts.extend(["## 四、结论", "", _md(pack.conclusion) or f"后续双路线设计围绕 {names} 展开。", ""])
    return "\n".join(parts)


def _candidate_block(candidate: Candidate) -> str:
    return "\n".join([
        f"### 候选 {candidate.id} — {candidate.epitope or '表位待标注'}（{candidate.format or '格式待标注'}）",
        f"- **VH**（{candidate.vh_germline or '胚系未标注'}）：",
        f"  `{candidate.vh}`",
        f"  - CDR-H1：{candidate.cdr_h1 or '—'}｜CDR-H2：{candidate.cdr_h2 or '—'}｜CDR-H3：{candidate.cdr_h3 or '—'}（{len(candidate.cdr_h3)} aa）",
        f"- **VL**（{candidate.vl_germline or '胚系未标注'}）：",
        f"  `{candidate.vl}`",
        f"  - CDR-L1：{candidate.cdr_l1 or '—'}｜CDR-L2：{candidate.cdr_l2 or '—'}｜CDR-L3：{candidate.cdr_l3 or '—'}（{len(candidate.cdr_l3)} aa）",
        f"- **格式/亚型**：{candidate.format or '—'}",
        f"- **预测表位**：{candidate.epitope or '—'}",
        f"- **预测亲和力**：{candidate.kd_pred}（预测，不是实测 KD）",
        f"- **特异性/脱靶**：{candidate.specificity or '—'}",
        "- **可开发性（设计时自述，快筛将用序列规则复核）**：",
        "",
        _table(
            ["维度", "评估"],
            [
                ["免疫原性", candidate.immunogenicity or "—"],
                ["聚集倾向", candidate.aggregation or "—"],
                ["Tm 趋势", candidate.tm or "—"],
                ["PTM（设计方备注）", candidate.ptm_note or "—"],
            ],
        ),
        "",
        f"- **设计策略**：{candidate.strategy or '—'}",
        f"- **优化方向**：{candidate.optimization or '—'}",
        "",
    ])


def render_design(
    title: str,
    expert: str,
    route_title: str,
    overview: str,
    candidates: List[Candidate],
    targets: List[TargetDossier],
    strategies: Dict[str, str],
    route_id: str,
    stamp: str,
    source_note: str,
) -> str:
    names = " / ".join(item.name for item in targets)
    parts = [
        f"# {expert}（{route_title}路线）抗体设计报告",
        "",
        f"> 路线：{route_title} ｜ 专家角色：{expert} ｜ 日期：{stamp}",
        f"> 靶点：{names}",
        f"> 候选数：{len(candidates)}",
        ">",
        f"> **声明**：{source_note} 结合表位、亲和力、特异性和可开发性均为预测或设计选择。"
        "本文件在结构程序实际跑通之前不写 iPTM / pLDDT。",
        "",
        "## 0. 路线说明",
        "",
        overview or f"本路线按 {route_title} 的设计侧重点，为每个靶点生成互补候选。",
        "",
    ]
    grouped: Dict[str, List[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.target].append(candidate)
    for index, target in enumerate(targets, start=1):
        rows = grouped.get(target.name, [])
        strategy = strategies.get(f"{route_id}:{target.slug}", "")
        parts.extend([
            f"# {index}. 靶点：{target.name}",
            "",
            "## 总体策略",
            "",
            strategy or target.design_points or "按该靶点的设计要点分配表位和格式。",
            "",
        ])
        if not rows:
            parts.append("本路线没有通过序列检查的候选。")
            parts.append("")
        for candidate in rows:
            parts.append(_candidate_block(candidate))
    return "\n".join(parts)


def render_fasta(candidates: Sequence[Candidate], stamp: str, route_label: str) -> str:
    lines = [
        f"# {route_label} 候选可变区",
        f"# 生成时间：{stamp}",
        "# 序列为设计序列。注释中的亲和力、表位均为预测。",
        "",
    ]
    for candidate in candidates:
        for chain, seq in (("VH", candidate.vh), ("VL", candidate.vl)):
            header = (
                f">{candidate.id}_{chain}|{candidate.vh_germline if chain == 'VH' else candidate.vl_germline}"
                f"|{candidate.format}|{candidate.epitope}|{candidate.kd_pred}"
            )
            lines.append(header.replace("\n", " "))
            lines.append(seq)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_sequence_index(candidates: Sequence[Candidate]) -> str:
    rows = []
    for candidate in candidates:
        rows.append([
            candidate.id,
            candidate.expert,
            candidate.target,
            candidate.epitope,
            candidate.format,
            candidate.vh_germline,
            candidate.vl_germline,
            str(len(candidate.cdr_h3)),
        ])
    return "\n".join([
        "# 双路线候选序列索引",
        "",
        "FASTA 见同目录 `02d`（博兹）和 `02e`（普腾）。下表只做检索。",
        "",
        _table(["编号", "路线", "靶点", "预测表位", "格式", "VH 胚系", "VL 胚系", "H3长度"], rows),
        "",
    ])


def render_dedup(report: DedupReport, candidates: Sequence[Candidate], stamp: str) -> str:
    parts = [
        "# 两路线候选去冗余核对报告",
        "",
        f"> 生成时间：{stamp}",
        "> 目的：在快筛前找出完全重复，以及独立设计但框架或 CDR 趋同的配对。",
        "",
        "## 一、结论摘要",
        "",
    ]
    for index, line in enumerate(report.summary_lines, start=1):
        parts.append(f"{index}. {line}")
    parts.extend([
        "",
        "## 二、完全重复",
        "",
        "\n".join(f"- {item}" for item in report.exact_duplicates) or "无。",
        "",
        "## 三、CDR-H3",
        "",
        "无重复。" if report.h3_unique else "\n".join(f"- {item}" for item in report.h3_collisions),
        "",
        "## 四、VH 胚系分布",
        "",
        _table(["胚系", "候选"], [[row["germline"], row["candidates"]] for row in report.vh_table]),
        "",
        "## 五、VL 胚系分布",
        "",
        _table(["胚系", "候选"], [[row["germline"], row["candidates"]] for row in report.vl_table]),
        "",
        "## 六、高相似配对（序列一致度 ≥ 0.90）",
        "",
    ])
    if report.groups:
        parts.append(_table(
            ["候选A", "候选B", "VH一致度", "VL一致度", "表位是否相同", "处理"],
            [[g["left"], g["right"], g["vh_identity"], g["vl_identity"], "是" if g["same_epitope"] else "否", g["advice"]] for g in report.groups],
        ))
    else:
        parts.append("没有达到阈值的配对。")
    parts.extend(["", f"核对序列共 {len(candidates)} 条。", ""])
    return "\n".join(parts)


def render_summary(candidates: Sequence[Candidate], stamp: str) -> str:
    grouped = _by_target(candidates)
    parts = [
        f"# 双路线候选抗体汇总清单（{len(candidates)}条）",
        "",
        f"> 生成时间：{stamp} ｜ 用途：快筛输入与汇编底稿",
        "",
    ]
    for target, rows in grouped.items():
        parts.extend([
            f"## {target} — {len(rows)} 条",
            "",
            _table(
                ["编号", "表位", "格式", "胚系 VH/VL", "KD（预测）", "设计方 PTM 备注", "路线"],
                [[
                    item.id,
                    item.epitope,
                    item.format,
                    f"{germline_token(item.vh_germline)}/{germline_token(item.vl_germline)}",
                    item.kd_pred,
                    item.ptm_note,
                    item.expert,
                ] for item in rows],
            ),
            "",
        ])
    return "\n".join(parts)


def _repair_hint(candidate: Candidate) -> str:
    gly = [hit for hit in candidate.ptm_hits if hit.in_cdr and hit.kind == "N-糖基化"]
    if not gly:
        return ""
    bits = []
    for hit in gly:
        if hit.motif[0] == "N":
            bits.append(f"{hit.chain} {hit.motif} 可评估 N→Q")
    return "；".join(bits)


def render_screen(
    candidates: Sequence[Candidate],
    tools: Sequence[ToolRun],
    stamp: str,
    source_note: str,
) -> str:
    passed = [item for item in candidates if item.screen_status == "通过"]
    conditional = [item for item in candidates if item.screen_status == "条件通过"]
    blocked = [item for item in candidates if item.screen_status == "过滤"]
    parts = [
        "# 快筛初筛报告",
        "",
        f"> 日期：{stamp}",
        f"> 输入：{len(candidates)} 条候选",
        ">",
        f"> **结论性质**：{source_note}",
        "> 可开发性里的 PTM、CDR 长度和打分来自本程序的序列规则，不是结构预测，也不是湿实验。",
        "> 只有计算软件真实回传的 iPTM/pLDDT 才会出现在「计算回传」一节。",
        "",
        "## 一、初筛方法",
        "",
        "1. 核对 CDR 注释是否落在 VH/VL 上；对不上时用 C…WGXG / C…FGXG 启发式仅补 H3/L3，并记入备注。",
        "2. 扫描 N-糖基化（N-X-S/T，X 不为 P）、脱酰胺（NG/NS/NN）、氧化（M）、异构化（DG/DS），并区分 CDR 与框架。",
        "3. CDR 区 N-糖基化直接过滤。可开发性分过低或 CDR 风险位点不少于 5 个时标为条件通过。",
        "4. 综合分 = 2.5 ×（功能 F + 特异性 S + 可开发性 D + 结构可行性 St）。F/S 来自设计步骤的自评分，D/St 由规则重算。",
        "5. 若配置了本地程序或 API，把回传指标并入候选；调用失败或没有指标时保持空白。",
        "",
        "## 二、逐条复核",
        "",
    ]
    for target, rows in _by_target(candidates).items():
        parts.append(f"### {target}")
        parts.append("")
        for candidate in rows:
            cdr_text = format_hits(candidate.ptm_hits, only_cdr=True)
            all_text = format_hits(candidate.ptm_hits, only_cdr=False)
            note = "；".join(candidate.notes) if candidate.notes else "无"
            parts.extend([
                f"**{candidate.id}**（{candidate.epitope}，{candidate.format}）",
                f"- 结构规则：{candidate.vh_germline} / {candidate.vl_germline}；CDR-H3 {len(candidate.cdr_h3)} aa（{candidate.cdr_h3 or '缺失'}）。",
                f"- PTM 复核（CDR）：{cdr_text}。全序列：{all_text}。设计方备注：{candidate.ptm_note or '无'}。",
                f"- 特异性（预测）：{candidate.specificity or '—'}",
                f"- 备注：{note}",
                f"- 结论：**{candidate.screen_status}**。F/S/D/St = {_score_text(candidate)}，综合 {candidate.composite:.0f}。{_repair_hint(candidate)}",
                "",
            ])
    parts.extend([
        "## 三、过滤与排名",
        "",
        f"- 通过 {len(passed)} 条；条件通过 {len(conditional)} 条；过滤 {len(blocked)} 条。",
        "",
    ])
    for target, rows in _by_target(candidates).items():
        parts.extend([
            f"### {target}",
            "",
            _table(
                ["排名", "编号", "表位", "格式", "KD（预测）", "F/S/D/St", "综合", "状态"],
                [[
                    str(rank),
                    item.id,
                    item.epitope,
                    item.format,
                    item.kd_pred,
                    _score_text(item),
                    f"{item.composite:.0f}",
                    item.screen_status,
                ] for rank, item in enumerate(rows, start=1)],
            ),
            "",
        ])
    parts.extend(["## 四、计算软件回传", ""])
    if not tools:
        parts.append("没有计算任务记录。")
    for run in tools:
        parts.append(f"- **{run.name}**（{run.kind}，{run.status}）：{run.detail}")
        if run.metrics_by_id:
            for cid, metrics in run.metrics_by_id.items():
                shown = "，".join(f"{key}={value}" for key, value in metrics.items())
                parts.append(f"  - {cid}：{shown}")
    parts.extend([
        "",
        "## 五、建议的下游工作",
        "",
        "下面是实验与复核建议，不是已经完成的实验：",
        "",
        "- 表达后做 SEC、AC-SINS，核对聚集；做差示扫描荧光或类似方法看热稳定性趋势。",
        "- 用 SPR 或 BLI 对靶点及近缘同源蛋白做结合，核对设计阶段写下的特异性风险。",
        "- 被 N-糖基化过滤的序列，优先评估 CDR 中 N→Q 后再重新跑本流程的快筛，而不是直接进入动物实验。",
        "- 若本地 Protenix、Boltz 或其他结构程序可用，把地址写进需求文件后重跑，用真实 iPTM/pLDDT 更新排序。",
        "",
    ])
    return "\n".join(parts)


def _top_passing(candidates: Sequence[Candidate], limit: int = 5) -> List[Candidate]:
    rows = [item for item in candidates if item.screen_status != "过滤"]
    rows.sort(key=lambda item: item.composite, reverse=True)
    return rows[:limit]


def render_final(
    spec: RequirementSpec,
    pack: ResearchPack,
    candidates: Sequence[Candidate],
    dedup: DedupReport,
    tools: Sequence[ToolRun],
    stamp: str,
    source_note: str,
) -> str:
    grouped = _by_target(candidates)
    blocked = [item for item in candidates if item.screen_status == "过滤"]
    parts = [
        f"# {spec.project_name}综合评估报告",
        "",
        f"> 日期：{stamp}",
        f"> 流程：要求分析 → 靶点调研 → 双路线设计（博兹 / 普腾）→ 本地计算（如已配置）→ 去冗余 → 快筛 → 汇编",
        ">",
        f"> **声明**：{source_note} 全部表位、亲和力、特异性和可开发性叙述都是 in-silico 预测，不能代替实验。",
        "",
        "# 第一部分：项目概述",
        "",
        "## 1.1 任务",
        "",
        spec.task_summary,
        "",
        "## 1.2 需求拆解",
        "",
        f"- 种属：{'；'.join(spec.species)}",
        f"- 理化：{'；'.join(spec.physicochemical)}",
        f"- 格式：{'；'.join(spec.formats)}",
        f"- 模态：{'；'.join(spec.modalities)}",
        f"- 其他：{spec.extra_constraints or '无'}",
        f"- 每路线每靶点：{spec.n_per_route_per_target} 条",
        "",
        "## 1.3 靶点",
        "",
        _table(
            ["靶点", "类型", "上市药", "核心设计命题"],
            [[item.name, item.mol_type, item.approved_drugs, item.design_points] for item in pack.selected],
        ),
        "",
        "## 1.4 多样性与去冗余",
        "",
    ]
    for line in dedup.summary_lines:
        parts.append(f"- {line}")
    parts.extend(["", "# 第二部分：候选总览", ""])
    if blocked:
        parts.append("硬过滤（CDR 区 N-糖基化）：" + "、".join(item.id for item in blocked) + "。")
    else:
        parts.append("没有因 CDR 区 N-糖基化被硬过滤的候选。")
    parts.append("")
    for target, rows in grouped.items():
        parts.extend([
            f"## {target}",
            "",
            _table(
                ["排名", "编号", "表位", "格式", "KD（预测）", "F/S/D/St", "综合", "状态"],
                [[str(i), item.id, item.epitope, item.format, item.kd_pred, _score_text(item), f"{item.composite:.0f}", item.screen_status] for i, item in enumerate(rows, start=1)],
            ),
            "",
        ])
    parts.extend(["# 第三部分：优先推进名单", ""])
    global_top = _top_passing(candidates, limit=8)
    parts.append(_table(
        ["优先级", "编号", "靶点", "综合", "状态", "进入下一步前"],
        [[str(i), item.id, item.target, f"{item.composite:.0f}", item.screen_status, item.optimization or "复核 PTM 与特异性"] for i, item in enumerate(global_top, start=1)],
    ))
    parts.extend(["", "分靶点建议先看每组综合分最高且状态为「通过」的候选。条件通过的条目先做序列修复，再进入结构预测或表达。", ""])
    if dedup.groups:
        parts.append("跨路线高相似配对：")
        parts.append("")
        for group in dedup.groups:
            parts.append(f"- {group['left']} 与 {group['right']}：{group['advice']}（VH {group['vh_identity']} / VL {group['vl_identity']}）")
        parts.append("")
    parts.extend(["# 第四部分：优先候选序列", ""])
    for target, rows in grouped.items():
        parts.append(f"## {target}")
        parts.append("")
        shown = 0
        for candidate in rows:
            if candidate.screen_status == "过滤":
                continue
            if shown >= 3:
                break
            shown += 1
            parts.extend([
                f"### {candidate.id}（{candidate.composite:.0f}分，{candidate.screen_status}）",
                "",
                f"- VH（{candidate.vh_germline}）：`{candidate.vh}`",
                f"- VL（{candidate.vl_germline}）：`{candidate.vl}`",
                f"- CDR-H3：{candidate.cdr_h3}｜表位：{candidate.epitope}｜格式：{candidate.format}",
                f"- 预测 KD：{candidate.kd_pred}｜特异性：{candidate.specificity}",
                f"- 规则 PTM（CDR）：{format_hits(candidate.ptm_hits, only_cdr=True)}",
                f"- 优化：{candidate.optimization or '—'}",
                "",
            ])
    parts.extend([
        "# 第五部分：计算与限制",
        "",
    ])
    for run in tools:
        parts.append(f"- {run.name}：{run.status}。{run.detail}")
    parts.extend([
        "",
        "未出现在上表中的结构分数，表示这次没有拿到对应的程序输出。不要把设计文字里的「预测亲和力」当成结构置信度。",
        "",
        "# 第六部分：文件索引",
        "",
        "- `00_靶点调研报告.md`",
        "- `01_博兹_BoltzMSA_抗体设计报告.md`",
        "- `02_普腾_ProtenixMSA_抗体设计报告.md`",
        "- `02b_双路线候选序列索引.md`",
        "- `02c_双路线去冗余核对报告.md`",
        "- `02d` / `02e` FASTA",
        "- `03_候选汇总清单.md`",
        "- `04_快筛初筛报告.md`",
        "- `05_综合评估报告.md`（本文件）",
        "- `06_综合评估报告.html`",
        "- `工作日志.md`、`完成概览.md`",
        "",
    ])
    return "\n".join(parts)


def render_html(
    spec: RequirementSpec,
    pack: ResearchPack,
    candidates: Sequence[Candidate],
    stamp: str,
) -> str:
    grouped = _by_target(candidates)
    blocked = sum(1 for item in candidates if item.screen_status == "过滤")
    passed = sum(1 for item in candidates if item.screen_status == "通过")
    cards = []
    for target in pack.selected:
        rows = grouped.get(target.name, [])
        best = next((item for item in rows if item.screen_status != "过滤"), None)
        cards.append(
            "<div class='card'><h3>{}</h3><p>{}</p><p class='best'>{}</p></div>".format(
                html.escape(target.name),
                html.escape(target.design_points or target.mol_type or ""),
                html.escape(
                    f"当前优先：{best.id}（{best.composite:.0f}）" if best else "没有通过快筛的候选"
                ),
            )
        )
    tables = []
    for target, rows in grouped.items():
        body = []
        for rank, item in enumerate(rows, start=1):
            body.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    rank,
                    html.escape(item.id),
                    html.escape(item.epitope),
                    html.escape(item.format),
                    f"{item.composite:.0f}",
                    html.escape(item.screen_status),
                )
            )
        tables.append(
            f"<h2>{html.escape(target)}</h2><table><thead><tr>"
            "<th>排名</th><th>编号</th><th>表位</th><th>格式</th><th>综合</th><th>状态</th>"
            f"</tr></thead><tbody>{''.join(body)}</tbody></table>"
        )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{html.escape(spec.project_name)}综合评估</title>
<style>
body {{ font-family: "Source Han Sans SC", "Noto Sans CJK SC", sans-serif; margin: 32px auto; max-width: 980px; color: #1c2430; line-height: 1.55; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.2rem; }}
.meta {{ color: #526070; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.card {{ border: 1px solid #d5dde6; border-radius: 10px; padding: 12px 14px; background: #f7fafc; }}
.best {{ font-weight: 650; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
th, td {{ border: 1px solid #d5dde6; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #e8eef4; }}
.note {{ background: #fff8e8; border-left: 4px solid #e0a100; padding: 8px 12px; }}
</style>
</head>
<body>
<h1>{html.escape(spec.project_name)}</h1>
<p class="meta">生成时间 {html.escape(stamp)} ｜ 候选 {len(list(candidates))} ｜ 通过 {passed} ｜ 过滤 {blocked}</p>
<p class="note">本页是序列规则与设计文字的汇编。亲和力、表位和特异性都是预测。没有计算软件回传时，页面不展示结构分数。</p>
<div class="cards">{''.join(cards)}</div>
{''.join(tables)}
</body>
</html>
"""


def render_worklog(
    spec: RequirementSpec,
    pack: ResearchPack,
    candidates: Sequence[Candidate],
    tools: Sequence[ToolRun],
    phases: Sequence[str],
    stamp: str,
    output_dir: Path,
) -> str:
    blocked = [item.id for item in candidates if item.screen_status == "过滤"]
    tops = _top_passing(candidates, 4)
    lines = [
        f"# {stamp[:10]} 工作日志",
        "",
        f"## {spec.project_name}",
        "",
        f"**任务**：{spec.task_summary}",
        "",
        "**执行过程**：",
        "",
    ]
    for phase in phases:
        lines.append(f"- {phase}")
    lines.extend([
        "",
        f"**靶点**：{'、'.join(item.name for item in pack.selected) or '无'}",
        f"**候选**：{len(list(candidates))} 条。过滤：{'、'.join(blocked) or '无'}。",
        "**优先**： " + ("；".join(f"{item.id}（{item.composite:.0f}）" for item in tops) or "无"),
        "",
        "**计算**：",
    ])
    for run in tools:
        lines.append(f"- {run.name}：{run.status}。{run.detail}")
    lines.extend([
        "",
        f"**交付目录**：`{output_dir}`",
        "",
        "结构分数和湿实验都没有在未运行的情况下补写。需要本地软件时，把 cli 或 api 地址写在需求文件的「计算软件」段落后重新运行。",
        "",
    ])
    return "\n".join(lines)


def render_overview(
    spec: RequirementSpec,
    pack: ResearchPack,
    candidates: Sequence[Candidate],
    stamp: str,
    output_dir: Path,
) -> str:
    grouped = _by_target(candidates)
    tops = _top_passing(candidates, 4)
    rows = []
    for target in pack.selected:
        best = next((item for item in grouped.get(target.name, []) if item.screen_status != "过滤"), None)
        rows.append([target.name, target.heat or "见调研报告", target.design_points or "—", best.id if best else "—"])
    file_rows = [
        ["00_靶点调研报告.md", "靶点筛选依据"],
        ["01_博兹_BoltzMSA_抗体设计报告.md", "博兹路线候选"],
        ["02_普腾_ProtenixMSA_抗体设计报告.md", "普腾路线候选"],
        ["02b_双路线候选序列索引.md", "序列索引"],
        ["02c_双路线去冗余核对报告.md", "去冗余"],
        ["02d / 02e FASTA", "可变区序列"],
        ["03_候选汇总清单", "汇总表"],
        ["04_快筛初筛报告.md", "规则快筛、过滤和打分"],
        ["05_综合评估报告.md", "主交付"],
        ["06_综合评估报告.html", "可视化版本"],
    ]
    return "\n".join([
        f"# {spec.project_name} · 完成概览",
        "",
        f"> 完成时间：{stamp}",
        "",
        "## 任务成果摘要",
        "",
        spec.task_summary,
        "",
        "### 靶点",
        "",
        _table(["靶点", "热度依据", "设计命题", "当前优先候选"], rows),
        "",
        f"### 候选",
        "",
        f"共 {len(list(candidates))} 条，来自博兹与普腾两条路线。",
        "",
        "### 优先顺序",
        "",
        "\n".join(
            f"{index}. **{item.id}**（{item.composite:.0f}，{item.target}，{item.screen_status}）"
            for index, item in enumerate(tops, start=1)
        ) or "没有可推进候选。",
        "",
        "## 关键文件",
        "",
        _table(["文件", "内容"], file_rows),
        "",
        f"目录：`{output_dir}`",
        "",
        "## 注意事项",
        "",
        "- 表位、KD、特异性和可开发性都是预测。",
        "- 未成功调用的计算软件不会产生结构分数。",
        "- 设计序列不能代替表达、结合和特异性实验。",
        "",
    ])


def write_reports(
    output_dir: Path,
    spec: RequirementSpec,
    pack: ResearchPack,
    candidates: List[Candidate],
    dedup: DedupReport,
    tools: Sequence[ToolRun],
    route_notes: Dict[str, str],
    strategies: Dict[str, str],
    phases: Sequence[str],
    source_note: str,
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    blz = [item for item in candidates if item.route_label == "BLZ"]
    prx = [item for item in candidates if item.route_label == "PRX"]
    files = {
        "00_靶点调研报告.md": render_research(pack, spec, stamp),
        "01_博兹_BoltzMSA_抗体设计报告.md": render_design(
            "博兹", "博兹", "Boltz·MSA", route_notes.get("boltz", ""), blz, pack.selected, strategies, "boltz", stamp, source_note
        ),
        "02_普腾_ProtenixMSA_抗体设计报告.md": render_design(
            "普腾", "普腾", "Protenix·MSA", route_notes.get("protenix", ""), prx, pack.selected, strategies, "protenix", stamp, source_note
        ),
        "02b_双路线候选序列索引.md": render_sequence_index(candidates),
        "02c_双路线去冗余核对报告.md": render_dedup(dedup, candidates, stamp),
        f"02d_BLZ_{len(blz)}候选_可变区序列.fasta": render_fasta(blz, stamp, "BLZ"),
        f"02e_PRX_{len(prx)}候选_可变区序列.fasta": render_fasta(prx, stamp, "PRX"),
        f"03_候选汇总清单_{len(candidates)}条.md": render_summary(candidates, stamp),
        "04_快筛初筛报告.md": render_screen(candidates, tools, stamp, source_note),
        "05_综合评估报告.md": render_final(spec, pack, candidates, dedup, tools, stamp, source_note),
        "06_综合评估报告.html": render_html(spec, pack, candidates, stamp),
    }
    written = []
    for name, content in files.items():
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    log_path = output_dir / "工作日志.md"
    overview_path = output_dir / "完成概览.md"
    log_path.write_text(render_worklog(spec, pack, candidates, tools, phases, stamp, output_dir), encoding="utf-8")
    overview_path.write_text(render_overview(spec, pack, candidates, stamp, output_dir), encoding="utf-8")
    written.extend([log_path, overview_path])
    return written
