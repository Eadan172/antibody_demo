#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""表格读写。识别误提交的 Git LFS 指针，避免把指针文本当成分子表。"""

import os

import pandas as pd


def read_table(path):
    """读取 CSV。文件不存在、或内容是 LFS 指针时抛出明确错误。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到数据文件: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        head = handle.read(80)
    if head.startswith("version https://git-lfs"):
        raise RuntimeError(
            f"{path} 是 Git LFS 指针，不是分子表。"
            "请先拉取 LFS 对象，或在演示模式使用 demo/data/ 下的示例文件。"
        )

    last_error = None
    for encoding in ("utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"无法读取 {path}: {last_error}")


def write_table(df, path):
    """写 CSV，并创建缺失的父目录。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False)
    return path
