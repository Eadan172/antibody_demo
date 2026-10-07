#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把当前脚本切到项目根目录的 .venv。首次运行时创建环境并安装演示依赖。"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


def project_root():
    return Path(__file__).resolve().parents[1]


def venv_python(root):
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def in_project_venv(root):
    venv_root = (root / ".venv").resolve()
    prefix = Path(sys.prefix).resolve()
    return prefix == venv_root or venv_root in prefix.parents


def ensure_project_venv():
    """不在项目 .venv 中时，创建环境、安装 requirements-demo.txt，然后用该解释器重新执行。"""
    if os.environ.get("MOLSCREEN_NO_VENV") == "1":
        return

    root = project_root()
    if in_project_venv(root):
        return

    python = venv_python(root)
    requirements = root / "requirements-demo.txt"
    if not requirements.is_file():
        raise SystemExit(f"缺少依赖清单: {requirements}")

    stamp = root / ".venv" / ".demo-deps-stamp"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not python.exists() or not stamp.is_file() or stamp.read_text(encoding="utf-8").strip() != digest:
        _create_or_update(root, python, requirements)
        stamp.write_text(digest + "\n", encoding="utf-8")

    if os.environ.get("MOLSCREEN_VENV_EXEC") == "1":
        raise SystemExit(f"已切换到 {python}，但该解释器没有把 {root / '.venv'} 当作虚拟环境。")

    print(f"使用虚拟环境: {root / '.venv'}", flush=True)
    os.environ["MOLSCREEN_VENV_EXEC"] = "1"
    os.execv(str(python), [str(python), *sys.argv])


def _has_pip(python):
    return subprocess.call(
        [str(python), "-m", "pip", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) == 0


def _create_or_update(root, python, requirements):
    venv_dir = root / ".venv"
    if not python.exists() or not _has_pip(python):
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        print(f"正在创建虚拟环境: {venv_dir}", flush=True)
        if not _create_venv(venv_dir, python):
            raise SystemExit(
                "无法创建带 pip 的 .venv。请确认当前 Python 带有 venv 模块，"
                "并且可以访问 https://bootstrap.pypa.io 以下载 pip。"
                " Debian/Ubuntu 也可以先执行: sudo apt install python3-venv"
            )
    print(f"正在向 .venv 安装 {requirements.name} ...", flush=True)
    try:
        subprocess.check_call([str(python), "-m", "pip", "install", "-r", str(requirements)])
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"安装 {requirements.name} 失败，退出码 {exc.returncode}") from exc


def _create_venv(venv_dir, python):
    """优先使用自带的 ensurepip。没有该模块时改为不装 pip 再建环境，然后用官方脚本补上 pip。"""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(venv_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        try:
            subprocess.check_call([sys.executable, "-m", "venv", "--without-pip", str(venv_dir)])
        except subprocess.CalledProcessError:
            return False
        if not _bootstrap_pip(python):
            return False
    return python.exists() and _has_pip(python)


def _bootstrap_pip(python):
    print("当前 Python 没有 ensurepip，正在下载 pip ...", flush=True)
    try:
        with urllib.request.urlopen("https://bootstrap.pypa.io/get-pip.py", timeout=60) as response:
            script = response.read()
    except Exception as exc:
        print(f"下载 pip 失败: {exc}")
        return False
    handle = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    try:
        handle.write(script)
        handle.close()
        result = subprocess.call([str(python), handle.name])
    finally:
        os.remove(handle.name)
    return result == 0
