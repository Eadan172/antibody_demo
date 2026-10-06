import json
from pathlib import Path

from antibody_pipeline.compute_runner import parse_metrics, run_cli_tool
from antibody_pipeline.models import Candidate, ComputeTool


def _candidate() -> Candidate:
    return Candidate(
        id="A-HER2-01",
        route="路线A",
        route_label="A",
        expert="路线A",
        target="HER2",
        epitope="远膜",
        format="IgG1",
        vh_germline="IGHV3-23",
        vl_germline="IGKV1-39",
        vh="A" * 110,
        vl="A" * 100,
    )


def test_parse_metrics_reads_common_envelopes():
    data = {"results": [{"id": "A-HER2-01", "iptm": 0.81, "plddt": 88, "ignored": 1}]}
    metrics = parse_metrics(data)
    assert metrics["A-HER2-01"]["iptm"] == 0.81
    assert "ignored" not in metrics["A-HER2-01"]


def test_missing_binary_is_skipped():
    tool = ComputeTool(name="fold_tool", kind="cli", address="/tmp/does-not-exist-fold")
    result = run_cli_tool(tool, Path("missing.fasta"), Path("."), timeout=5)
    assert result.status == "skipped"
    assert result.metrics_by_id == {}


def test_cli_json_is_applied(tmp_path: Path):
    script = tmp_path / "fake_predict.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "outdir = pathlib.Path(sys.argv[2])\n"
        "(outdir / 'results.json').write_text(json.dumps({'results': [{'id': 'A-HER2-01', 'iptm': 0.77, 'plddt': 81}]}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fasta = tmp_path / "in.fasta"
    fasta.write_text(">A-HER2-01_VH\nAAAA\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    tool = ComputeTool(
        name="fake",
        kind="cli",
        address="python3",
        command="python3 {program} {fasta} {outdir}".replace("{program}", str(script)),
    )
    # command 模板会再替换 {program}。这里直接把脚本路径放进模板。
    tool.command = f"python3 {script} {{fasta}} {{outdir}}"
    tool.address = "python3"
    result = run_cli_tool(tool, fasta, work, timeout=20)
    assert result.status == "ok"
    assert result.metrics_by_id["A-HER2-01"]["plddt"] == 81
    candidate = _candidate()
    from antibody_pipeline.compute_runner import run_compute_tools

    runs = run_compute_tools([tool], [candidate], fasta, tmp_path / "out", timeout=20)
    assert runs[0].status == "ok"
    assert candidate.compute_metrics["iptm"] == 0.77
    json.loads((work / "results.json").read_text(encoding="utf-8"))
