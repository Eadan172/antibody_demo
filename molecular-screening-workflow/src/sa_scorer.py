#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合成可及性评分。有 RDKit SA Score 时使用它，否则使用确定性占位分。"""

import os
import sys

import pandas as pd

from io_utils import write_table

Chem = None
sascorer = None

try:
    from rdkit import Chem
    from rdkit.Chem import RDConfig

    sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
    import sascorer
except ImportError:
    pass


def calculate_sa_score(smiles):
    """返回 1–10 的 SA Score。无法计算时返回 None。"""
    if sascorer is None or Chem is None or pd.isna(smiles):
        return None
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None
        return float(sascorer.calculateScore(mol))
    except Exception:
        return None


def fallback_sa_score(smiles):
    """没有 SA Score 模块时的占位分，只随 SMILES 长度变化。"""
    if pd.isna(smiles):
        return None
    return round(min(8.0, max(1.5, len(str(smiles)) / 12.0)), 3)


def run_sa_filter(df, threshold=6.0, output_path="results/05_sa.csv", sort=True):
    print("=" * 60)
    print("步骤5: SA Score评估")
    print("=" * 60)

    frame = df.copy()
    if "SMILES" not in frame.columns:
        raise ValueError("SA Score 输入缺少 SMILES 列")

    if sascorer is None:
        print("SA Score 模块不可用，使用按 SMILES 长度计算的占位分")
        frame["sa_score"] = frame["SMILES"].map(fallback_sa_score)
        frame["sa_mode"] = "fallback"
    else:
        frame["sa_score"] = frame["SMILES"].map(calculate_sa_score)
        frame["sa_mode"] = "rdkit"

    frame = frame.dropna(subset=["sa_score"])
    if frame.empty:
        write_table(frame, output_path)
        print(f"没有可评分的分子 -> {output_path}")
        return frame

    print(
        f"SA Score 范围: {frame['sa_score'].min():.2f} - {frame['sa_score'].max():.2f}"
    )
    filtered = frame[frame["sa_score"] <= float(threshold)].copy()
    if sort:
        filtered = filtered.sort_values("sa_score")
    write_table(filtered, output_path)
    print(f"阈值 {threshold}: {len(filtered)} / {len(frame)} -> {output_path}")
    return filtered


if __name__ == "__main__":
    print(calculate_sa_score("CC(=O)Oc1ccccc1C(=O)O"))
