#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成模块测试
"""

import sys
import os
import json
sys.path.insert(0, '..')

from antibody_virtual_screening import generate_report, AntibodyCandidate


def create_mock_candidate(id_suffix, stability=80.0, solubility=70.0):
    """创建模拟抗体候选"""
    return AntibodyCandidate(
        id=f"AB_{id_suffix}",
        sequence="EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK",
        stability_score=stability,
        solubility_score=solubility,
        immunogenicity_score=25.0,
        binding_affinity=0.5
    )


def test_generate_report_structure():
    """测试报告结构完整性"""
    candidates = [
        create_mock_candidate("0001"),
        create_mock_candidate("0002"),
    ]
    
    report = generate_report(candidates, 100)
    
    # 检查必要字段
    assert "timestamp" in report
    assert "summary" in report
    assert "top_candidates" in report
    assert "recommendations" in report
    
    # 检查summary字段
    assert report["summary"]["total_input"] == 100
    assert report["summary"]["passed_count"] == 2
    
    print("✅ test_generate_report_structure 通过")


def test_generate_report_file():
    """测试报告文件输出"""
    candidates = [create_mock_candidate("0001")]
    output_path = "test_report_output.json"
    
    report = generate_report(candidates, 50, output_path)
    
    # 检查文件是否生成
    assert os.path.exists(output_path)
    
    # 读取并验证内容
    with open(output_path, 'r') as f:
        loaded = json.load(f)
        assert loaded["summary"]["total_input"] == 50
    
    # 清理测试文件
    os.remove(output_path)
    print("✅ test_generate_report_file 通过")


def test_generate_report_ranking():
    """测试报告中的排名是否正确"""
    candidates = [
        create_mock_candidate("0001", stability=80.0),
        create_mock_candidate("0002", stability=90.0),
        create_mock_candidate("0003", stability=85.0),
    ]
    
    report = generate_report(candidates, 100)
    
    # 检查排名
    assert report["top_candidates"][0]["rank"] == 1
    assert report["top_candidates"][1]["rank"] == 2
    assert report["top_candidates"][2]["rank"] == 3
    
    # 最高分应该是AB_0002
    assert report["top_candidates"][0]["id"] == "AB_0002"
    
    print("✅ test_generate_report_ranking 通过")


if __name__ == "__main__":
    test_generate_report_structure()
    test_generate_report_file()
    test_generate_report_ranking()
    print("\n🎉 所有报告生成测试通过！")
