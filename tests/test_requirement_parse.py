from antibody_pipeline.parse_input import parse_requirement_hints


def test_example_requirements_keep_targets_and_count():
    text = open("input/requirements.txt", encoding="utf-8").read()
    hints = parse_requirement_hints(text, default_n=6)
    assert hints["targets"] == ["CDH17", "B7-H3（CD276）", "CLDN6"]
    assert hints["n_per_route_per_target"] == 2
    assert hints["compute_tools"] == []
    assert "调研" in hints["task_text"]


def test_compute_tool_lines():
    text = """
任务
做抗体

指定靶点
CD20

每路线每靶点候选数
4

计算软件
# 这一行忽略
fold_tool | cli | /opt/fold/bin/predict | {program} --input {fasta} --out {outdir} |
fold_api | api | http://127.0.0.1:8080/predict | | secret-token
"""
    hints = parse_requirement_hints(text, default_n=6)
    assert hints["n_per_route_per_target"] == 4
    assert [tool.name for tool in hints["compute_tools"]] == ["fold_tool", "fold_api"]
    assert hints["compute_tools"][0].kind == "cli"
    assert hints["compute_tools"][1].kind == "api"
    assert hints["compute_tools"][1].token == "secret-token"


def test_custom_design_routes_override_defaults():
    text = """
设计路线
内化优先 | IN | 偏膜近端与快速内化
阻断优先 | BK | 偏功能阻断
"""
    hints = parse_requirement_hints(text, default_n=6)
    assert [item["name"] for item in hints["routes"]] == ["内化优先", "阻断优先"]
    assert [item["prefix"] for item in hints["routes"]] == ["IN", "BK"]
    assert "内化" in hints["routes"][0]["focus"]
