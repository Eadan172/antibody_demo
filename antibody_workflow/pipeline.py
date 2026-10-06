"""从自然语言需求到可审计交付物的主编排流程。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings, TaskRequest, parse_task_file
from .llm import LLMClient
from .reporting import markdown_to_html, value_to_markdown, write_markdown
from .research import collect_research
from .tools import run_tools


class Workflow:
    def __init__(self, task_file: Path, request: TaskRequest, settings: Settings):
        self.task_file = task_file
        self.request = request
        self.settings = settings
        self.client = LLMClient(settings)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_dir = Path(request.output_dir) / f"{request.project_name}-{stamp}"
        self.raw_dir = self.output_dir / "raw"

    def run(self) -> Path:
        self.raw_dir.mkdir(parents=True, exist_ok=False)
        self._write_manifest("running")

        analysis = self._ask(
            "00_analysis",
            f"""分析以下抗体项目需求，提取明确约束、隐含假设、缺失信息，并制定执行阶段。
需求原文：
{self.request.requirements}""",
            """{
  "summary": "需求摘要",
  "targets": ["靶点"],
  "constraints": ["理化性质/种属/模态/数量等硬约束"],
  "assumptions": ["必须由用户或实验确认的假设"],
  "research_queries": ["适合 PubMed 的英文检索式"],
  "workflow": ["阶段与验收标准"],
  "risk_controls": ["证据与生物安全边界"]
}""",
        )
        write_markdown(
            self.output_dir / "00_需求分析与任务拆解.md",
            "需求分析与任务拆解",
            [(key, value_to_markdown(value)) for key, value in analysis.items()],
        )

        queries = self.request.research_queries or _string_list(analysis.get("research_queries"))
        records, research_errors = collect_research(queries[:8])
        self._write_json("literature_records", {"queries": queries, "records": records, "errors": research_errors})
        research = self._ask(
            "01_research",
            f"""根据需求与下列 PubMed 检索记录撰写靶点/项目调研。不得引用记录之外的具体论文；
每项具体文献事实在正文中使用 [PMID:编号]。若证据不足，明确列入 evidence_gaps。
需求分析：{_compact(analysis)}
检索记录：{_compact(records)}""",
            """{
  "report_markdown": "含筛选方法、靶点生物学、竞争格局、结构可设计性、种属与脱靶风险的正文",
  "evidence_table": [{"claim":"结论","pmids":["123"],"confidence":"高/中/低"}],
  "evidence_gaps": ["待进一步核验项"],
  "recommended_strategy": ["有证据支持的策略"]
}""",
        )
        write_markdown(
            self.output_dir / "01_靶点调研报告.md",
            "靶点调研报告",
            [
                ("调研正文", value_to_markdown(research.get("report_markdown", ""))),
                ("证据索引", _literature_markdown(records)),
                ("证据缺口", value_to_markdown(research.get("evidence_gaps", []))),
            ],
        )

        design = self._ask(
            "02_design",
            f"""提出可进入计算筛选的抗体设计方案。候选数量服从需求；若需求未指定，每个靶点最多4条。
允许生成候选 VH/VL 序列，但必须标为“未验证设计序列”，不得声称真实亲和力、结构分数或实验效果。
每条候选应覆盖不同表位/骨架/模态，并给出 PTM、聚集、免疫原性、种属和脱靶检查计划。
需求：{_compact(analysis)}
调研：{_compact(research)}""",
            """{
  "strategy_markdown": "总体设计原则与路线差异",
  "candidates": [{
    "id":"唯一编号","target":"靶点","route":"设计路线","format":"IgG/scFv等",
    "epitope_hypothesis":"预测表位","species_goal":"种属要求",
    "vh":"氨基酸序列或空字符串","vl":"氨基酸序列或空字符串",
    "sequence_status":"未验证设计序列","rationale":"设计理由",
    "risks":["风险"],"required_validation":["验证"]
  }],
  "design_gaps": ["无法仅靠LLM完成的事项"]
}""",
            temperature=0.35,
        )
        candidates = design.get("candidates", [])
        write_markdown(
            self.output_dir / "02_候选设计报告.md",
            "候选抗体设计报告",
            [
                ("设计策略", value_to_markdown(design.get("strategy_markdown", ""))),
                ("候选明细", _candidate_markdown(candidates)),
                ("设计缺口", value_to_markdown(design.get("design_gaps", []))),
            ],
        )
        _write_fasta(self.output_dir / "02b_候选可变区序列.fasta", candidates)
        write_markdown(
            self.output_dir / "03_候选汇总清单.md",
            "候选抗体汇总清单",
            [("候选清单", _candidate_table(candidates))],
        )

        tool_results = run_tools(
            self.request.tools,
            task_file=self.task_file,
            output_dir=self.output_dir,
            context={
                "requirements": self.request.requirements,
                "analysis": analysis,
                "candidates": candidates,
            },
        )
        screening = self._ask(
            "04_screening",
            f"""基于候选信息和真实工具执行清单做初筛。只有 status=completed 且对应结果文件中实际出现的指标
才可称为“计算结果”；没有配置工具或工具失败时必须写“未计算”，只能做序列规则检查。
候选：{_compact(candidates)}
工具执行清单：{_compact(tool_results)}""",
            """{
  "methodology":"已执行与未执行的方法",
  "candidate_assessments":[{"id":"编号","status":"通过/条件通过/过滤/未计算","observations":["观察"],"computed_evidence":["真实计算证据或未计算"],"risks":["风险"],"next_actions":["行动"]}],
  "ranking":[{"id":"编号","tier":"A/B/C/待计算","reason":"理由"}],
  "missing_computations":["缺失计算"],
  "experimental_plan":["实验验证"]
}""",
        )
        write_markdown(
            self.output_dir / "04_计算与快筛报告.md",
            "计算与快速初筛报告",
            [
                ("方法与证据边界", value_to_markdown(screening.get("methodology", ""))),
                ("工具执行清单", _tool_markdown(tool_results)),
                ("逐条评估", value_to_markdown(screening.get("candidate_assessments", []))),
                ("分层排序", value_to_markdown(screening.get("ranking", []))),
                ("缺失计算", value_to_markdown(screening.get("missing_computations", []))),
                ("实验计划", value_to_markdown(screening.get("experimental_plan", []))),
            ],
        )

        final = self._ask(
            "05_final",
            f"""汇总项目为可交付的决策报告。不得把模型预测升级为计算或实验事实。
需求分析：{_compact(analysis)}
调研结论：{_compact(research)}
候选设计：{_compact(design)}
快筛：{_compact(screening)}""",
            """{
  "executive_summary":"执行摘要",
  "requirement_traceability":["每项原始要求如何满足或尚未满足"],
  "recommendations":["分层推荐及理由"],
  "evidence_boundaries":["公开事实/模型推断/计算/实验四类边界"],
  "next_steps":["按依赖关系排序的下一步"],
  "limitations":["局限"]
}""",
        )
        final_path = self.output_dir / "05_综合评估报告.md"
        write_markdown(
            final_path,
            "抗体项目综合评估报告",
            [(key, value_to_markdown(value)) for key, value in final.items()],
        )
        html_path = self.output_dir / "06_综合评估报告.html"
        html_path.write_text(
            markdown_to_html(final_path.read_text(encoding="utf-8"), "抗体项目综合评估报告"),
            encoding="utf-8",
        )
        self._write_overview(records, candidates, tool_results)
        self._write_manifest("completed")
        return self.output_dir

    def _ask(
        self, name: str, prompt: str, schema: str, temperature: float = 0.2
    ) -> dict[str, Any]:
        result = self.client.ask_json(prompt, schema_hint=schema, temperature=temperature)
        self._write_json(name, result)
        return result

    def _write_json(self, name: str, value: Any) -> None:
        (self.raw_dir / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _write_manifest(self, status: str) -> None:
        manifest = {
            "status": status,
            "project": self.request.project_name,
            "task_file": str(self.task_file.resolve()),
            "model": self.settings.model,
            "base_url": self.settings.base_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "api_key_stored": False,
        }
        (self.output_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _write_overview(
        self,
        records: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> None:
        write_markdown(
            self.output_dir / "overview.md",
            "项目交付概览",
            [
                ("项目", self.request.project_name),
                ("产出统计", f"- PubMed 记录：{len(records)}\n- 候选：{len(candidates)}\n- 计算工具：{len(tools)}"),
                (
                    "文件清单",
                    "\n".join(f"- `{path.name}`" for path in sorted(self.output_dir.iterdir())),
                ),
            ],
        )


def run_workflow(task_file: Path, root: Path | None = None) -> Path:
    request = parse_task_file(task_file)
    settings = Settings.from_env(root or Path.cwd())
    return Workflow(task_file, request, settings).run()


def _compact(value: Any, limit: int = 45000) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…[截断]"


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _literature_markdown(records: list[dict[str, Any]]) -> str:
    if not records:
        return "PubMed 未返回可用记录；报告中的具体文献事实均应视为待核验。"
    return "\n".join(
        f"- [PMID:{item['pmid']}]({item['url']}) {item['title']} ({item['date']})"
        for item in records
    )


def _candidate_markdown(candidates: Any) -> str:
    if not isinstance(candidates, list) or not candidates:
        return "模型未生成结构化候选。"
    chunks = []
    for item in candidates:
        chunks.append(
            f"### {item.get('id', '未命名')}\n"
            f"- 靶点：{item.get('target', '')}\n"
            f"- 路线/格式：{item.get('route', '')} / {item.get('format', '')}\n"
            f"- 表位假设：{item.get('epitope_hypothesis', '')}\n"
            f"- 序列状态：{item.get('sequence_status', '未验证设计序列')}\n"
            f"- 设计理由：{item.get('rationale', '')}\n"
            f"- 风险：{'; '.join(_string_list(item.get('risks')))}\n"
            f"- 必要验证：{'; '.join(_string_list(item.get('required_validation')))}"
        )
    return "\n\n".join(chunks)


def _candidate_table(candidates: Any) -> str:
    rows = ["| ID | 靶点 | 路线 | 格式 | 表位假设 | 序列状态 |", "|---|---|---|---|---|---|"]
    for item in candidates if isinstance(candidates, list) else []:
        rows.append(
            "| {id} | {target} | {route} | {format} | {epitope} | {status} |".format(
                id=item.get("id", ""),
                target=item.get("target", ""),
                route=item.get("route", ""),
                format=item.get("format", ""),
                epitope=item.get("epitope_hypothesis", ""),
                status=item.get("sequence_status", "未验证设计序列"),
            )
        )
    return "\n".join(rows)


def _write_fasta(path: Path, candidates: Any) -> None:
    lines = ["# 所有序列均为未验证的 in-silico 设计，不是实验结果。"]
    for item in candidates if isinstance(candidates, list) else []:
        for chain in ("vh", "vl"):
            sequence = str(item.get(chain, "")).replace(" ", "").replace("\n", "").upper()
            if sequence:
                lines.extend([f">{item.get('id', 'candidate')}_{chain.upper()}|UNVERIFIED_DESIGN", sequence])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tool_markdown(results: list[dict[str, Any]]) -> str:
    if not results:
        return "未配置本地或 API 计算工具；本次没有真实结构/能量计算结果。"
    return "\n".join(
        f"- **{item['name']}**（{item['kind']}）：{item['status']}；"
        f"{item.get('result_file') or item.get('stdout_file') or item.get('error', '')}"
        for item in results
    )
