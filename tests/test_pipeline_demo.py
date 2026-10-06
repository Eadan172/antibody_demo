from pathlib import Path

from antibody_pipeline.pipeline import run_pipeline


def test_demo_writes_the_deliverable_set(tmp_path: Path):
    output = tmp_path / "run"
    run_pipeline(
        input_path=Path("input/requirements.txt"),
        output_dir=output,
        config_path=Path("config.yaml"),
        demo=True,
        project_root=Path.cwd(),
    )
    names = {path.name for path in output.iterdir() if path.is_file()}
    for expected in [
        "00_靶点调研报告.md",
        "01_博兹_BoltzMSA_抗体设计报告.md",
        "02_普腾_ProtenixMSA_抗体设计报告.md",
        "02b_双路线候选序列索引.md",
        "02c_双路线去冗余核对报告.md",
        "04_快筛初筛报告.md",
        "05_综合评估报告.md",
        "06_综合评估报告.html",
        "工作日志.md",
        "完成概览.md",
    ]:
        assert expected in names
    fasta = [name for name in names if name.endswith(".fasta")]
    assert any(name.startswith("02d_BLZ_") for name in fasta)
    assert any(name.startswith("02e_PRX_") for name in fasta)
    assert any(name.startswith("03_候选汇总清单_") for name in names)
    screen = (output / "04_快筛初筛报告.md").read_text(encoding="utf-8")
    assert "BLZ-HER2-02" in screen
    assert "过滤" in screen
    assert "iPTM" in screen
    assert "iptm=" not in screen
    html = (output / "06_综合评估报告.html").read_text(encoding="utf-8")
    assert "HER2" in html
    assert "离线演示" in (output / "完成概览.md").read_text(encoding="utf-8")
    log = (output / "工作日志.md").read_text(encoding="utf-8")
    assert "要求" in log or "阶段" in log


def test_resume_skips_redesign(tmp_path: Path):
    output = tmp_path / "run"
    run_pipeline(
        input_path=Path("input/requirements.txt"),
        output_dir=output,
        config_path=Path("config.yaml"),
        demo=True,
        project_root=tmp_path,
    )
    marker = output / "05_综合评估报告.md"
    first = marker.read_text(encoding="utf-8")
    run_pipeline(
        input_path=Path("input/requirements.txt"),
        output_dir=output,
        config_path=Path("config.yaml"),
        demo=False,
        resume=True,
        project_root=tmp_path,
    )
    second = marker.read_text(encoding="utf-8")
    assert "BLZ-HER2-01" in first
    assert "BLZ-HER2-01" in second
