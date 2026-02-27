#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抗体药物虚拟筛选Demo
作者：Eadan172
功能：基于理化特征的抗体药物快速排序与筛选
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime

# ==================== 配置区 ====================
CONFIG = {
    "stability_threshold": 75.0,      # 稳定性阈值
    "solubility_threshold": 60.0,     # 溶解度阈值
    "immunogenicity_threshold": 30.0,  # 免疫原性阈值（越低越好）
    "top_k": 5,                       # 输出Top-K结果
    "batch_size": 100                 # 批处理大小
}

# ==================== 数据模型 ====================
@dataclass
class AntibodyCandidate:
    """抗体候选药物数据模型"""
    id: str
    sequence: str
    stability_score: float      # 0-100，越高越稳定
    solubility_score: float     # 0-100，越高溶解度越好
    immunogenicity_score: float # 0-100，越低免疫原性风险越小
    binding_affinity: float     # KD值，越小亲和力越强
    
    @property
    def composite_score(self) -> float:
        """综合评分：加权计算"""
        return (
            self.stability_score * 0.3 +
            self.solubility_score * 0.25 +
            (100 - self.immunogenicity_score) * 0.25 +
            min(100, 100 / (self.binding_affinity + 1)) * 0.2
        )

# ==================== 模块1：数据输入与清洗 ====================
def load_antibody_data(raw_data: List[Dict]) -> List[AntibodyCandidate]:
    """
    加载并清洗抗体数据
    防御性编程：字段校验、类型转换、异常处理
    """
    candidates = []
    
    for idx, record in enumerate(raw_data):
        try:
            # 字段完整性检查
            required_fields = ['id', 'sequence', 'stability_score', 
                             'solubility_score', 'immunogenicity_score', 'binding_affinity']
            if not all(field in record for field in required_fields):
                logging.warning(f"记录 {idx} 缺少必要字段，已跳过")
                continue
            
            # 类型转换与有效性检查
            candidate = AntibodyCandidate(
                id=str(record['id']),
                sequence=str(record['sequence']).upper(),
                stability_score=float(record['stability_score']),
                solubility_score=float(record['solubility_score']),
                immunogenicity_score=float(record['immunogenicity_score']),
                binding_affinity=float(record['binding_affinity'])
            )
            
            # 业务规则校验
            if len(candidate.sequence) < 50:
                logging.warning(f"抗体 {candidate.id} 序列过短，可能不完整")
                continue
                
            candidates.append(candidate)
            
        except (ValueError, TypeError) as e:
            logging.error(f"记录 {idx} 数据格式错误: {e}")
            continue
    
    logging.info(f"成功加载 {len(candidates)}/{len(raw_data)} 条抗体数据")
    return candidates

# ==================== 模块2：业务逻辑处理 ====================
def screen_antibodies(
    candidates: List[AntibodyCandidate],
    config: Dict
) -> List[AntibodyCandidate]:
    """
    抗体虚拟筛选核心逻辑
    基于多维度理化特征进行过滤与排序
    """
    filtered = []
    
    for antibody in candidates:
        # 硬约束：必须满足最低阈值
        if antibody.stability_score < config['stability_threshold']:
            continue
        if antibody.solubility_score < config['solubility_threshold']:
            continue
        if antibody.immunogenicity_score > config['immunogenicity_threshold']:
            continue
            
        filtered.append(antibody)
    
    # 软排序：按综合评分降序
    ranked = sorted(filtered, key=lambda x: x.composite_score, reverse=True)
    
    logging.info(
        f"筛选完成：{len(candidates)} → {len(filtered)} "
        f"通过率 {len(filtered)/len(candidates)*100:.1f}%"
    )
    return ranked[:config['top_k']]

# ==================== 模块3：结果输出与通知 ====================
def generate_report(
    top_antibodies: List[AntibodyCandidate],
    total_input: int,
    output_path: Optional[str] = None
) -> Dict:
    """
    生成筛选报告并输出
    支持JSON文件保存与控制台打印

    为了简化上层调用，函数会在内部根据候选抗体的综合评分
    对传入列表进行降序排序，这样即便调用者未先调用
    ``screen_antibodies``也能得到正确的排名结果。
    """
    # 确保传入的候选列表按综合评分降序排列
    if top_antibodies:
        top_antibodies = sorted(
            top_antibodies,
            key=lambda ab: ab.composite_score,
            reverse=True,
        )

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_input": total_input,
            "passed_count": len(top_antibodies),
            "pass_rate": f"{len(top_antibodies)/total_input*100:.1f}%"
        },
        "top_candidates": [
            {
                "rank": idx + 1,
                **asdict(ab),
                "composite_score": round(ab.composite_score, 2)
            }
            for idx, ab in enumerate(top_antibodies)
        ],
        "recommendations": [
            f"优先推进候选抗体 {ab.id}（综合评分: {ab.composite_score:.1f}）"
            for ab in top_antibodies[:3]
        ]
    }
    
    # 控制台输出
    print("\n" + "="*50)
    print("🧬 抗体AI虚拟筛选报告")
    print("="*50)
    print(f"输入样本数: {total_input}")
    print(f"通过筛选: {len(top_antibodies)} | 通过率: {report['summary']['pass_rate']}")
    print("\n🏆 Top候选抗体:")
    for item in report['top_candidates']:
        print(f"  {item['rank']}. {item['id']} | 综合评分: {item['composite_score']}")
    
    # 文件输出
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logging.info(f"报告已保存至: {output_path}")
    
    return report

# ==================== 主流程 ====================
def main():
    """主执行函数"""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # 模拟1000条抗体数据（实际场景从数据库/文件读取）
    mock_data = [
        {
            "id": f"AB_{i:04d}",
            "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTALYYCAK",
            "stability_score": 60 + (i % 40),
            "solubility_score": 50 + (i % 50),
            "immunogenicity_score": 20 + (i % 60),
            "binding_affinity": 0.1 + (i % 100) / 100
        }
        for i in range(1000)
    ]
    
    # 执行流程
    candidates = load_antibody_data(mock_data)
    top_antibodies = screen_antibodies(candidates, CONFIG)
    report = generate_report(top_antibodies, len(mock_data), "screening_report.json")
    
    return report

if __name__ == "__main__":
    main()
