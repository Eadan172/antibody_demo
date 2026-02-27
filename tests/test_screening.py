#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选逻辑模块测试
"""

import sys
sys.path.insert(0, '..')

from antibody_virtual_screening import screen_antibodies, AntibodyCandidate


def create_mock_candidate(
    id_suffix,
    stability=80.0,
    solubility=70.0,
    immunogenicity=25.0,
    affinity=0.5
):
    """创建模拟抗体候选"""
    return AntibodyCandidate(
        id=f"AB_{id_suffix}",
        sequence="EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK",
        stability_score=stability,
        solubility_score=solubility,
        immunogenicity_score=immunogenicity,
        binding_affinity=affinity
    )


def test_screen_all_pass():
    """测试全部通过的筛选"""
    config = {
        "stability_threshold": 75.0,
        "solubility_threshold": 60.0,
        "immunogenicity_threshold": 30.0,
        "top_k": 3
    }
    
    candidates = [
        create_mock_candidate("0001", stability=90.0),
        create_mock_candidate("0002", stability=85.0),
        create_mock_candidate("0003", stability=80.0),
    ]
    
    result = screen_antibodies(candidates, config)
    assert len(result) == 3
    print("✅ test_screen_all_pass 通过")


def test_screen_partial_pass():
    """测试部分通过的筛选"""
    config = {
        "stability_threshold": 75.0,
        "solubility_threshold": 60.0,
        "immunogenicity_threshold": 30.0,
        "top_k": 5
    }
    
    candidates = [
        create_mock_candidate("0001", stability=90.0),   # 通过
        create_mock_candidate("0002", stability=70.0),   # 不通过（稳定性不足）
        create_mock_candidate("0003", stability=85.0),   # 通过
    ]
    
    result = screen_antibodies(candidates, config)
    assert len(result) == 2  # 只有2个通过
    print("✅ test_screen_partial_pass 通过")


def test_screen_ranking():
    """测试排序是否正确"""
    config = {
        "stability_threshold": 75.0,
        "solubility_threshold": 60.0,
        "immunogenicity_threshold": 30.0,
        "top_k": 3
    }
    
    candidates = [
        create_mock_candidate("0001", stability=80.0, solubility=70.0),
        create_mock_candidate("0002", stability=90.0, solubility=80.0),  # 应该排第一
        create_mock_candidate("0003", stability=85.0, solubility=75.0),
    ]
    
    result = screen_antibodies(candidates, config)
    assert result[0].id == "AB_0002"  # 综合评分最高
    print("✅ test_screen_ranking 通过")


def test_screen_top_k():
    """测试Top-K限制"""
    config = {
        "stability_threshold": 75.0,
        "solubility_threshold": 60.0,
        "immunogenicity_threshold": 30.0,
        "top_k": 2  # 只取前2个
    }
    
    candidates = [
        create_mock_candidate("0001", stability=80.0),
        create_mock_candidate("0002", stability=90.0),
        create_mock_candidate("0003", stability=85.0),
        create_mock_candidate("0004", stability=88.0),
    ]
    
    result = screen_antibodies(candidates, config)
    assert len(result) == 2  # 只返回2个
    print("✅ test_screen_top_k 通过")


if __name__ == "__main__":
    test_screen_all_pass()
    test_screen_partial_pass()
    test_screen_ranking()
    test_screen_top_k()
    print("\n🎉 所有筛选逻辑测试通过！")
