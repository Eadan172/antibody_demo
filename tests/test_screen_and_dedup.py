from antibody_pipeline.dedup import build_dedup
from antibody_pipeline.demo_data import build_demo
from antibody_pipeline.scoring import screen_all
from antibody_pipeline.sequence_analysis import chain_problem


def test_demo_sequences_are_variable_regions_and_filter_glycosylation():
    _spec, _pack, rows, _notes, _strategies = build_demo()
    for candidate in rows:
        assert chain_problem(candidate.vh, "VH") == ""
        assert chain_problem(candidate.vl, "VL") == ""
    screen_all(rows)
    blocked = next(item for item in rows if item.id == "A-HER2-02")
    assert blocked.screen_status == "过滤"
    assert any(hit.kind == "N-糖基化" and hit.in_cdr and hit.cdr_name == "L3" for hit in blocked.ptm_hits)
    clean = next(item for item in rows if item.id == "A-HER2-01")
    assert clean.screen_status != "过滤"
    assert clean.composite > blocked.composite


def test_shared_light_chain_is_reported_without_merging_different_epitopes():
    _spec, _pack, rows, _notes, _strategies = build_demo()
    report = build_dedup(rows)
    assert any("VL 完全一致" in line and "A-HER2-01" in line and "B-HER2-01" in line for line in report.exact_duplicates)
    pair = next(group for group in report.groups if {group["left"], group["right"]} == {"A-HER2-01", "B-HER2-01"})
    assert pair["same_epitope"] is False
    assert "不合并" in pair["advice"]
    assert report.h3_unique
