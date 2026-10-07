#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ADMET 过滤。缺少预测列时按配置中的目标值填充，并在日志中标明这是占位值。"""

import pandas as pd

from io_utils import write_table

try:
    from rdkit import Chem
except ImportError:
    Chem = None

DEFAULT_CRITERIA = {
    "P-gp_substrate": 0,
    "P-gp_I_inhibitor": 0,
    "P-gp_II_inhibitor": 0,
    "CYP2D6_substrate": 0,
    "CYP3A4_substrate": 0,
    "CYP1A2_inhibitor": 0,
    "CYP2C19_inhibitor": 0,
    "CYP2C9_inhibitor": 0,
    "AMES_toxicity": 0,
    "hERG_II_inhibitor": 0,
    "Hepatotoxicity": 0,
    "Skin_Sensitisation": 0,
}


def smiles_to_mol(smiles):
    if Chem is None or pd.isna(smiles):
        return None
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is not None:
            Chem.SanitizeMol(mol)
        return mol
    except Exception:
        return None


def run_admet_filter(df, criteria=None, output_path="results/03_admet.csv"):
    """按 criteria 中的列做等值过滤。缺列时填入目标值，使演示流程可以继续。"""
    print("=" * 60)
    print("步骤3: ADMET性质过滤")
    print("=" * 60)

    criteria = dict(criteria or DEFAULT_CRITERIA)
    frame = df.copy()
    filled = []
    for column, expected in criteria.items():
        if column not in frame.columns:
            frame[column] = expected
            filled.append(column)
    if filled:
        print(
            "以下 ADMET 列不存在，已按配置目标值填充，不是模型预测: "
            + ", ".join(filled)
        )

    query = " & ".join(f"`{key}` == {value}" for key, value in criteria.items())
    passed = frame.query(query).copy()
    write_table(passed, output_path)
    print(f"ADMET 过滤后剩余 {len(passed)} / {len(frame)} -> {output_path}")
    return passed


def run_druglike_filter(df, output_path="results/ADMET/druglike_passed.csv"):
    """Lipinski 规则过滤。不在主流程中调用。"""
    try:
        from rdkit.Chem import Descriptors
    except ImportError:
        print("警告: 缺少 rdkit，跳过类药物性质筛选")
        return df

    def passes(mol):
        if mol is None:
            return False
        return (
            Descriptors.MolWt(mol) < 500
            and Descriptors.MolLogP(mol) < 5
            and Descriptors.NumHDonors(mol) < 5
            and Descriptors.NumHAcceptors(mol) < 10
        )

    frame = df.copy()
    frame["druglike_pass"] = frame["SMILES"].apply(smiles_to_mol).apply(passes)
    passed = frame[frame["druglike_pass"]].drop(columns=["druglike_pass"])
    write_table(passed, output_path)
    return passed
