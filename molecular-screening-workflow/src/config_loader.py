#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 workflow_config.yaml 的嵌套结构展开成工作流使用的一份配置。"""

import os

DEFAULT_ADMET_CRITERIA = {
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

STEP_OUTPUTS = ("generated", "qsar", "admet", "docking", "sa", "plots")


def _section(raw, key):
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ValueError(f"配置项 {key} 必须是映射，当前类型为 {type(value).__name__}")
    return value


def load_raw_config(config_path):
    """读取 YAML。缺少 PyYAML 或文件不存在时直接失败，避免静默退回空配置。"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("缺少 pyyaml。请安装: pip install pyyaml") from exc

    with open(config_path, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"配置文件根节点必须是映射: {config_path}")
    return loaded


def resolve_config(raw, demo_mode=False):
    """展开嵌套配置。演示模式只覆盖数据路径，筛选阈值仍来自同一份 YAML。"""
    raw = raw or {}
    data = _section(raw, "data")
    models = _section(raw, "models")
    rnn = _section(raw, "rnn")
    qsar = _section(raw, "qsar")
    admet = _section(raw, "admet")
    docking = _section(raw, "docking")
    sa_score = _section(raw, "sa_score")
    output = _section(raw, "output")
    demo = _section(raw, "demo")

    results_dir = output.get("results_dir", "results")
    paths = {
        "generated": output.get("generated", os.path.join(results_dir, "01_generated.csv")),
        "qsar": output.get("qsar", os.path.join(results_dir, "02_qsar.csv")),
        "admet": output.get("admet", os.path.join(results_dir, "03_admet.csv")),
        "docking": output.get("docking", os.path.join(results_dir, "04_docking.csv")),
        "sa": output.get("sa", os.path.join(results_dir, "05_sa.csv")),
        "plots": output.get("plots", os.path.join(results_dir, "evaluation_summary.png")),
        "logs_dir": output.get("logs_dir", "logs"),
        "results_dir": results_dir,
    }

    criteria = admet.get("criteria") or dict(DEFAULT_ADMET_CRITERIA)
    engines = docking.get("engines") or ["vina"]
    if isinstance(engines, str):
        engines = [engines]

    resolved = {
        "demo_mode": bool(demo_mode),
        "rnn_train_data": data.get("rnn_train_data", "data/merged_rnn_data.csv"),
        "qsar_train_data": data.get("qsar_train_data", "data/merged_qsar_data.csv"),
        "demo_molecules": demo.get("molecules", "demo/data/sample_molecules.csv"),
        "rnn_model": models.get("rnn_model", "models/selfies_generator_rnn.keras"),
        "qsar_model": models.get("qsar_model", "models/ultimate_ensemble_qsar_model.pkl"),
        "num_molecules": int(rnn.get("num_molecules", 500)),
        "temperature": float(rnn.get("temperature", 0.7)),
        "top_k": int(rnn.get("top_k", 50)),
        "epochs": int(rnn.get("epochs", 200)),
        "batch_size": int(rnn.get("batch_size", 128)),
        "ic50_threshold": float(qsar.get("ic50_threshold", 100)),
        "top_n": int(qsar.get("top_n", 100)),
        "test_size": float(qsar.get("test_size", 0.2)),
        "admet_criteria": criteria,
        "docking_engines": list(engines),
        "receptor_pdb": docking.get("receptor_pdb", "pdb_files_AKT1/4gv1.pdb"),
        "docking_box": docking.get("box") or {},
        "sa_threshold": float(sa_score.get("threshold", 6.0)),
        "sa_sort": bool(sa_score.get("sort", True)),
        "paths": paths,
    }

    if demo_mode:
        resolved["rnn_train_data"] = demo.get("rnn_train_data", "demo/data/sample_training.csv")
        resolved["qsar_train_data"] = demo.get("qsar_train_data", "demo/data/sample_training.csv")
        resolved["demo_molecules"] = demo.get("molecules", "demo/data/sample_molecules.csv")

    return resolved
