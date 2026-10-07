#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QSAR 活性预测。

演示模式用确定性占位分数，不训练模型。
正式预测只加载已经保存的 pipeline。
训练需要显式执行 python src/qsar_engine.py --train。
"""

import math
import os
import pickle

import pandas as pd

from io_utils import read_table, write_table


def qsar_predict_and_filter(
    train_data_path,
    predict_data_path,
    model_path,
    output_path,
    demo_mode=False,
    top_n=100,
    ic50_threshold=100,
    test_size=0.2,
):
    """预测 IC50 并按阈值与 top_n 过滤。train_data_path / test_size 仅训练时使用。"""
    print("=" * 60)
    print("步骤2: QSAR活性预测")
    print("=" * 60)
    del train_data_path, test_size

    table = read_table(predict_data_path)
    if "SMILES" not in table.columns:
        raise ValueError(f"{predict_data_path} 缺少 SMILES 列")
    table = table.dropna(subset=["SMILES"]).copy()
    table["SMILES"] = table["SMILES"].astype(str)

    if demo_mode:
        print("演示模式: 写入确定性占位活性，不是已训练模型的预测")
        table["pred_IC50"] = table["SMILES"].map(_demo_ic50_nm)
        table["pIC50"] = table["pred_IC50"].map(_pic50_from_nm)
        table["qsar_mode"] = "demo"
        _attach_properties(table)
    else:
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"未找到 QSAR 模型: {model_path}。"
                "请先训练: python src/qsar_engine.py --train"
            )
        with open(model_path, "rb") as handle:
            pipeline = pickle.load(handle)
        features = _descriptor_frame(table["SMILES"])
        valid = features.notna().all(axis=1)
        table = table.loc[valid].copy()
        features = features.loc[valid]
        if table.empty:
            raise ValueError("没有可计算描述符的分子")
        predicted_pic50 = pipeline.predict(features)
        table["pIC50"] = predicted_pic50
        table["pred_IC50"] = [float(10 ** (9 - value)) for value in predicted_pic50]
        table["qsar_mode"] = "model"
        _attach_properties(table)

    before = len(table)
    filtered = table[table["pred_IC50"] <= float(ic50_threshold)].copy()
    filtered = filtered.sort_values("pred_IC50").head(int(top_n))
    write_table(filtered, output_path)
    print(
        f"阈值 {ic50_threshold} nM、top_n={top_n}: "
        f"{len(filtered)} / {before} -> {output_path}"
    )
    return filtered


def train_qsar_model(train_data_path, model_path, test_size=0.2):
    """训练描述符回归模型。目标是 pIC50。没有单位列时把 IC50 视为 nM。"""
    frame = read_table(train_data_path)
    for column in ("SMILES", "IC50"):
        if column not in frame.columns:
            raise ValueError(f"{train_data_path} 缺少 {column} 列")

    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, VotingRegressor
    from sklearn.feature_selection import SelectKBest, f_regression
    from sklearn.metrics import mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    frame = frame.dropna(subset=["SMILES", "IC50"]).copy()
    frame["IC50_nM"] = [
        _to_nm(value, unit)
        for value, unit in zip(
            frame["IC50"],
            frame["IC50_unit"] if "IC50_unit" in frame.columns else ["nM"] * len(frame),
        )
    ]
    frame = frame[frame["IC50_nM"] > 0].copy()
    features = _descriptor_frame(frame["SMILES"].astype(str))
    labels = frame["IC50_nM"].map(_pic50_from_nm)
    mask = features.notna().all(axis=1) & labels.notna()
    features = features.loc[mask]
    labels = labels.loc[mask]
    if len(features) < 5:
        raise ValueError("可用于训练的分子少于 5 个")

    splitter = train_test_split
    x_train, x_val, y_train, y_val = splitter(
        features, labels, test_size=test_size, random_state=42
    )
    k = min(150, x_train.shape[1])
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("feature_selection", SelectKBest(f_regression, k=k)),
            (
                "regressor",
                VotingRegressor(
                    [
                        ("rf", RandomForestRegressor(n_estimators=300, max_depth=30, random_state=42, n_jobs=-1)),
                        ("gb", GradientBoostingRegressor(n_estimators=300, max_depth=7, learning_rate=0.1, random_state=42)),
                    ]
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    predicted = pipeline.predict(x_val)
    r2 = float(r2_score(y_val, predicted))
    rmse = float(np.sqrt(mean_squared_error(y_val, predicted)))
    print(f"验证集 pIC50 R²={r2:.4f}  RMSE={rmse:.4f}")

    parent = os.path.dirname(model_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(model_path, "wb") as handle:
        pickle.dump(pipeline, handle)
    print(f"模型已保存: {model_path}")
    return {"r2_pic50": r2, "rmse_pic50": rmse}


def _demo_ic50_nm(smiles):
    """由 SMILES 得到稳定的 10–189 nM 占位值，便于阈值过滤留下一部分分子。"""
    total = sum(ord(char) for char in smiles)
    return float(10 + (total % 180))


def _pic50_from_nm(ic50_nm):
    return 9.0 - math.log10(float(ic50_nm))


def _to_nm(value, unit):
    numeric = float(value)
    label = str(unit or "nM").strip().lower()
    if label in {"nm", "nanomolar"}:
        return numeric
    if label in {"um", "µm", "μm", "micromolar"}:
        return numeric * 1000.0
    if label in {"mm", "millimolar"}:
        return numeric * 1_000_000.0
    raise ValueError(f"无法识别的 IC50 单位: {unit}")


def _descriptor_frame(smiles_series):
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    rows = []
    for smiles in smiles_series:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            rows.append({})
            continue
        rows.append(Descriptors.CalcMolDescriptors(mol))
    frame = pd.DataFrame(rows)
    frame.index = smiles_series.index
    return frame.apply(pd.to_numeric, errors="coerce")


def _attach_properties(table):
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
    except ImportError:
        return table

    weights = []
    logps = []
    for smiles in table["SMILES"]:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            weights.append(None)
            logps.append(None)
        else:
            weights.append(Descriptors.MolWt(mol))
            logps.append(Descriptors.MolLogP(mol))
    table["MW"] = weights
    table["LogP"] = logps
    return table


if __name__ == "__main__":
    import argparse

    from config_loader import load_raw_config, resolve_config

    parser = argparse.ArgumentParser(description="QSAR 预测。训练与预测分开。")
    parser.add_argument("--config", default="config/workflow_config.yaml")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--input", help="待预测 CSV，默认读上一步生成结果")
    cli = parser.parse_args()
    config = resolve_config(load_raw_config(cli.config), demo_mode=cli.demo)
    if cli.train:
        train_qsar_model(
            config["qsar_train_data"],
            config["qsar_model"],
            test_size=config["test_size"],
        )
    else:
        source = cli.input or config["paths"]["generated"]
        qsar_predict_and_filter(
            config["qsar_train_data"],
            source,
            config["qsar_model"],
            config["paths"]["qsar"],
            demo_mode=cli.demo,
            top_n=config["top_n"],
            ic50_threshold=config["ic50_threshold"],
            test_size=config["test_size"],
        )
