"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="antibody-workflow",
        description="从自然语言抗体需求生成可审计的调研、计算与评估报告。",
    )
    parser.add_argument("task_file", type=Path, help="UTF-8 需求文本文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output_dir = run_workflow(args.task_file)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"\n完成。交付目录：{output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
