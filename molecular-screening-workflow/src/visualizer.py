#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结果图。安装了 matplotlib 时画四格图，否则写一张不依赖第三方库的 PNG。"""

import os
import struct
import zlib

import pandas as pd

plt = None
sns = None

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
except ImportError:
    pass


def generate_plots(final_df, qsar_results=None, output_path="results/evaluation_summary.png"):
    print("=" * 60)
    print("步骤6: 结果可视化")
    print("=" * 60)
    del qsar_results

    if final_df is None or len(final_df) == 0:
        print("警告: 没有数据可供可视化")
        _write_fallback_png(pd.DataFrame({"pred_IC50": []}), output_path)
        return output_path

    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if plt is None:
        print("未安装 matplotlib，写入占位 PNG")
        _write_fallback_png(final_df, output_path)
        print(f"可视化图表已保存至: {output_path}")
        return output_path

    frame = final_df.copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    _plot_ic50_distribution(frame, axes[0, 0])
    _plot_chemical_space(frame, axes[0, 1])
    _plot_sa_score_distribution(frame, axes[1, 0])
    _plot_top_candidates(frame, axes[1, 1])
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"可视化图表已保存至: {output_path}")
    return output_path


def _plot_ic50_distribution(df, ax):
    if "pred_IC50" not in df.columns:
        ax.text(0.5, 0.5, "No IC50 Data", ha="center", va="center")
        return
    sns.histplot(data=df, x="pred_IC50", bins=20, color="skyblue", kde=True, ax=ax)
    ax.set_xlabel("Predicted IC50 (nM)")
    ax.set_ylabel("Count")
    ax.set_title("IC50 Distribution")
    ax.axvline(x=100, color="red", linestyle="--", label="Threshold (100 nM)")
    ax.legend()


def _plot_chemical_space(df, ax):
    frame = df
    if "MW" not in frame.columns or "LogP" not in frame.columns:
        if "SMILES" in frame.columns:
            frame = _calculate_properties(frame.copy())
        else:
            ax.text(0.5, 0.5, "No Property Data", ha="center", va="center")
            return
    if "MW" not in frame.columns or frame["MW"].dropna().empty:
        ax.text(0.5, 0.5, "No Property Data", ha="center", va="center")
        return
    hue_col = "sa_score" if "sa_score" in frame.columns else None
    sns.scatterplot(data=frame, x="MW", y="LogP", hue=hue_col, palette="viridis", alpha=0.6, ax=ax)
    ax.set_xlabel("Molecular Weight (Da)")
    ax.set_ylabel("LogP")
    ax.set_title("Chemical Space Distribution")


def _plot_sa_score_distribution(df, ax):
    if "sa_score" not in df.columns:
        ax.text(0.5, 0.5, "No SA Score Data", ha="center", va="center")
        return
    sns.boxplot(data=df, y="sa_score", color="lightgreen", ax=ax)
    ax.set_ylabel("SA Score")
    ax.set_title("SA Score Distribution")
    ax.axhline(y=6.0, color="red", linestyle="--", label="Threshold (6.0)")
    ax.legend()


def _plot_top_candidates(df, ax):
    if "pred_IC50" not in df.columns:
        ax.text(0.5, 0.5, "No IC50 Data", ha="center", va="center")
        return
    top_n = min(20, len(df))
    if "sa_score" in df.columns:
        top_df = df.nsmallest(top_n, "sa_score")
    else:
        top_df = df.nsmallest(top_n, "pred_IC50")
    top_df = top_df.reset_index(drop=True)
    top_df["rank"] = range(1, len(top_df) + 1)
    sns.barplot(data=top_df, x="rank", y="pred_IC50", color="steelblue", ax=ax)
    ax.set_xlabel("Rank")
    ax.set_ylabel("Predicted IC50 (nM)")
    ax.set_title(f"Top {top_n} Candidates")
    ax.tick_params(axis="x", rotation=45)


def _calculate_properties(df):
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
    except ImportError:
        return df

    weights = []
    logps = []
    for smiles in df["SMILES"]:
        mol = Chem.MolFromSmiles(str(smiles)) if pd.notna(smiles) else None
        if mol is None:
            weights.append(None)
            logps.append(None)
        else:
            weights.append(Descriptors.MolWt(mol))
            logps.append(Descriptors.MolLogP(mol))
    df["MW"] = weights
    df["LogP"] = logps
    return df


def _write_fallback_png(df, output_path):
    """用标准库写一张 480x240 的柱状图，保证演示模式不依赖 matplotlib。"""
    width, height = 480, 240
    values = []
    if df is not None and "pred_IC50" in getattr(df, "columns", []):
        values = [float(value) for value in df["pred_IC50"].dropna().head(24)]
    peak = max(values) if values else 1.0
    columns = max(len(values), 1)
    gap = 4
    bar_width = max(2, (width - 20) // columns - gap)

    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend(b"\xf4\xf7\xfb")
        rows.append(row)

    for index, value in enumerate(values):
        bar_height = int((value / peak) * (height - 30))
        x0 = 10 + index * (bar_width + gap)
        for y in range(height - 10 - bar_height, height - 10):
            if y < 0 or y >= height:
                continue
            for x in range(x0, min(width, x0 + bar_width)):
                rows[y][x * 3 : x * 3 + 3] = b"\x2f\x6f\xad"

    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "wb") as handle:
        handle.write(png)


def generate_summary_report(df, output_path="results/summary_report.txt"):
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(f"分子数: {0 if df is None else len(df)}\n")
        if df is not None and "pred_IC50" in df.columns and len(df):
            handle.write(f"pred_IC50 最小: {df['pred_IC50'].min():.2f} nM\n")
            handle.write(f"pred_IC50 中位: {df['pred_IC50'].median():.2f} nM\n")
        if df is not None and "sa_score" in df.columns and len(df):
            handle.write(f"sa_score 平均: {df['sa_score'].mean():.2f}\n")
    print(f"摘要报告已保存至: {output_path}")
