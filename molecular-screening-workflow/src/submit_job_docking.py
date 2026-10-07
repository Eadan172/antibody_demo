#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分子对接。演示模式写占位结合能；正式模式读取配置中的引擎、受体和对接盒。"""

import hashlib
import json
import os

import pandas as pd

from io_utils import read_table, write_table

Chem = None
AllChem = None
SDWriter = None

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, SDWriter
except ImportError:
    pass

try:
    from requests_toolbelt.multipart.encoder import MultipartEncoder
except ImportError:
    MultipartEncoder = None

ENGINE_URLS = {
    "vina": "https://neurosnap.ai/api/job/submit/AutoDock Vina (smina)?note=molecular-screening-workflow",
    "autodock-vina": "https://neurosnap.ai/api/job/submit/AutoDock Vina (smina)?note=molecular-screening-workflow",
    "gnina": "https://neurosnap.ai/api/job/submit/GNINA?note=molecular-screening-workflow",
    "diffdock": "https://neurosnap.ai/api/job/submit/DiffDock-L",
    "diffdock-l": "https://neurosnap.ai/api/job/submit/DiffDock-L",
}


def csv_to_sdf(csv_file, sdf_file):
    """把含 SMILES 列的 CSV 写成 SDF。"""
    if Chem is None or SDWriter is None or AllChem is None:
        raise RuntimeError("缺少 rdkit，无法把分子写成 SDF")

    frame = read_table(csv_file)
    parent = os.path.dirname(sdf_file)
    if parent:
        os.makedirs(parent, exist_ok=True)
    writer = SDWriter(sdf_file)
    written = 0
    try:
        for index, row in frame.iterrows():
            mol = Chem.MolFromSmiles(str(row["SMILES"]))
            if mol is None:
                print(f"无法解析 SMILES: {row['SMILES']} (行 {index})")
                continue
            AllChem.Compute2DCoords(mol)
            for column in frame.columns:
                mol.SetProp(str(column), str(row[column]))
            writer.write(mol)
            written += 1
    finally:
        writer.close()
    print(f"SDF 已写入 {written} 个分子 -> {sdf_file}")
    return written


def submit_docking_job(
    docking_engine=None,
    input_csv="results/03_admet.csv",
    output_csv="results/04_docking.csv",
    demo_mode=False,
    receptor_pdb=None,
    box=None,
):
    """演示模式不访问网络。正式模式提交任务，但不在这一阶段等待结果。"""
    print("=" * 60)
    print("步骤4: 分子对接")
    print("=" * 60)

    engines = docking_engine or ["vina"]
    if isinstance(engines, str):
        engines = [engines]
    engine = engines[0]
    box = box or {}
    print(f"对接引擎: {engine}")
    if box:
        print(
            "对接盒: "
            f"center=({box.get('center_x')}, {box.get('center_y')}, {box.get('center_z')}) "
            f"size=({box.get('size_x')}, {box.get('size_y')}, {box.get('size_z')})"
        )

    if demo_mode:
        print("演示模式: 写入占位结合能，不提交对接任务")
        frame = read_table(input_csv)
        if "SMILES" not in frame.columns:
            raise ValueError(f"{input_csv} 缺少 SMILES 列")
        frame = frame.copy()
        frame["binding_affinity"] = frame["SMILES"].map(_demo_affinity)
        frame["rmsd_lb"] = 0.0
        frame["rmsd_ub"] = 1.0
        frame["docking_mode"] = "demo"
        frame["docking_engine"] = engine
        write_table(frame, output_csv)
        print(f"写入 {len(frame)} 行 -> {output_csv}")
        return frame

    if engine not in ENGINE_URLS:
        known = ", ".join(sorted(ENGINE_URLS))
        raise ValueError(f"未知对接引擎 {engine}。可选: {known}")
    if not receptor_pdb or not os.path.exists(receptor_pdb):
        raise FileNotFoundError(f"找不到受体 PDB: {receptor_pdb}")
    api_key = os.environ.get("NEUROSNAP_API_KEY")
    if not api_key:
        raise RuntimeError("未设置环境变量 NEUROSNAP_API_KEY，无法提交在线对接")
    if MultipartEncoder is None:
        raise RuntimeError("缺少 requests_toolbelt，无法提交在线对接")

    sdf_file = os.path.splitext(output_csv)[0] + "_ligands.sdf"
    csv_to_sdf(input_csv, sdf_file)
    import requests

    with open(receptor_pdb, "rb") as receptor_handle, open(sdf_file, "r", encoding="utf-8") as ligand_handle:
        ligand_text = ligand_handle.read()
        payload = MultipartEncoder(
            fields={
                "Input Receptor": ("structure.pdb", receptor_handle, "chemical/x-pdb"),
                "Input Ligand": json.dumps([{"data": ligand_text, "type": "sdf"}]),
            }
        )
        response = requests.post(
            ENGINE_URLS[engine],
            headers={"X-API-KEY": api_key, "Content-Type": payload.content_type},
            data=payload,
            timeout=120,
        )
    response.raise_for_status()
    job_id = response.json()
    record = {
        "job_id": job_id,
        "engine": engine,
        "receptor_pdb": receptor_pdb,
        "box": box,
        "ligand_sdf": sdf_file,
    }
    record_path = os.path.splitext(output_csv)[0] + "_job.json"
    parent = os.path.dirname(record_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    raise RuntimeError(
        f"对接任务已提交，任务 ID: {job_id}。结果文件 {record_path}。"
        "当前版本不轮询分数，因此还不能写出带结合能的 CSV。"
    )


def _demo_affinity(smiles):
    digest = hashlib.md5(str(smiles).encode("utf-8")).hexdigest()
    unit = int(digest[:4], 16) / 0xFFFF
    return round(-12.0 + 6.0 * unit, 3)


if __name__ == "__main__":
    submit_docking_job(demo_mode=True)
