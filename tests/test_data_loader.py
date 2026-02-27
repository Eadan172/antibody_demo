#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据加载模块测试
"""

import sys
sys.path.insert(0, '..')

from antibody_virtual_screening import load_antibody_data, AntibodyCandidate


def test_load_valid_data():
    """测试正常数据加载"""
    raw_data = [
        {
            "id": "AB_0001",
            "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK",
            "stability_score": 85.0,
            "solubility_score": 70.0,
            "immunogenicity_score": 25.0,
            "binding_affinity": 0.5
        }
    ]
    
    result = load_antibody_data(raw_data)
    assert len(result) == 1
    assert result[0].id == "AB_0001"
    print("✅ test_load_valid_data 通过")


def test_load_missing_field():
    """测试缺少字段的数据"""
    raw_data = [
        {
            "id": "AB_0002",
            "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK"
            # 缺少其他字段
        }
    ]
    
    result = load_antibody_data(raw_data)
    assert len(result) == 0  # 应该被过滤掉
    print("✅ test_load_missing_field 通过")


def test_load_short_sequence():
    """测试序列过短的抗体"""
    raw_data = [
        {
            "id": "AB_0003",
            "sequence": "EVQLV",  # 序列太短
            "stability_score": 85.0,
            "solubility_score": 70.0,
            "immunogenicity_score": 25.0,
            "binding_affinity": 0.5
        }
    ]
    
    result = load_antibody_data(raw_data)
    assert len(result) == 0  # 应该被过滤掉
    print("✅ test_load_short_sequence 通过")


def test_load_invalid_type():
    """测试类型错误的数据"""
    raw_data = [
        {
            "id": "AB_0004",
            "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK",
            "stability_score": "invalid",  # 应该是数字
            "solubility_score": 70.0,
            "immunogenicity_score": 25.0,
            "binding_affinity": 0.5
        }
    ]
    
    result = load_antibody_data(raw_data)
    assert len(result) == 0  # 应该被过滤掉
    print("✅ test_load_invalid_type 通过")


if __name__ == "__main__":
    test_load_valid_data()
    test_load_missing_field()
    test_load_short_sequence()
    test_load_invalid_type()
    print("\n🎉 所有数据加载测试通过！")
