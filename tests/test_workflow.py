import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from antibody_workflow.config import Settings, parse_task_file
from antibody_workflow.pipeline import Workflow


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def ask_json(self, prompt, *, schema_hint, temperature=0.2):
        self.calls += 1
        responses = [
            {
                "summary": "CLDN6 抗体项目",
                "targets": ["CLDN6"],
                "constraints": ["区分 CLDN9"],
                "assumptions": ["种属交叉待验证"],
                "research_queries": ["CLDN6 antibody"],
                "workflow": ["调研", "设计", "筛选"],
                "risk_controls": ["不得虚构计算值"],
            },
            {
                "report_markdown": "公开证据不足时待核验。",
                "evidence_table": [],
                "evidence_gaps": ["需实验"],
                "recommended_strategy": ["ECL2"],
            },
            {
                "strategy_markdown": "双路线设计。",
                "candidates": [
                    {
                        "id": "TEST-01",
                        "target": "CLDN6",
                        "route": "route-a",
                        "format": "IgG1",
                        "epitope_hypothesis": "ECL2",
                        "species_goal": "human/cyno",
                        "vh": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWV",
                        "vl": "DIQMTQSPSSLSASVGDRVTITCRASQSVSSYLNWYQQKPGKAPKLLI",
                        "sequence_status": "未验证设计序列",
                        "rationale": "测试",
                        "risks": ["未验证"],
                        "required_validation": ["SPR"],
                    }
                ],
                "design_gaps": ["需结构计算"],
            },
            {
                "methodology": "未配置计算工具，结构指标未计算。",
                "candidate_assessments": [],
                "ranking": [{"id": "TEST-01", "tier": "待计算", "reason": "无计算"}],
                "missing_computations": ["结构预测"],
                "experimental_plan": ["SPR"],
            },
            {
                "executive_summary": "完成可审计设计。",
                "requirement_traceability": ["CLDN9: 待验证"],
                "recommendations": ["先计算"],
                "evidence_boundaries": ["序列为模型设计"],
                "next_steps": ["结构预测"],
                "limitations": ["无实验数据"],
            },
        ]
        return responses[self.calls - 1]


class ConfigTests(unittest.TestCase):
    def test_plain_text_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.txt"
            path.write_text("设计抗 CLDN6 抗体", encoding="utf-8")
            task = parse_task_file(path)
            self.assertEqual(task.requirements, "设计抗 CLDN6 抗体")
            self.assertEqual(task.project_name, "request")

    def test_configured_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.txt"
            path.write_text(
                """---config
[project]
name = demo
research_queries =
  query one
  query two
[local_tool:test]
command = python tool.py --input {input}
---end
需求正文""",
                encoding="utf-8",
            )
            task = parse_task_file(path)
            self.assertEqual(task.project_name, "demo")
            self.assertEqual(task.research_queries, ["query one", "query two"])
            self.assertEqual(task.tools[0].kind, "local")


class WorkflowTests(unittest.TestCase):
    @patch("antibody_workflow.pipeline.collect_research", return_value=([], []))
    def test_end_to_end_with_fake_llm(self, _research):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_file = root / "request.txt"
            task_file.write_text("设计抗 CLDN6 抗体", encoding="utf-8")
            request = parse_task_file(task_file)
            request.output_dir = str(root / "outputs")
            workflow = Workflow(
                task_file,
                request,
                Settings("secret-key", "https://example.invalid/v1", "fake-model"),
            )
            workflow.client = FakeLLM()
            output = workflow.run()

            expected = [
                "00_需求分析与任务拆解.md",
                "01_靶点调研报告.md",
                "02_候选设计报告.md",
                "02b_候选可变区序列.fasta",
                "03_候选汇总清单.md",
                "04_计算与快筛报告.md",
                "05_综合评估报告.md",
                "06_综合评估报告.html",
                "overview.md",
                "run_manifest.json",
            ]
            for name in expected:
                self.assertTrue((output / name).exists(), name)

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "completed")
            self.assertNotIn("secret-key", (output / "run_manifest.json").read_text())
            self.assertIn("UNVERIFIED_DESIGN", (output / "02b_候选可变区序列.fasta").read_text())


if __name__ == "__main__":
    unittest.main()
