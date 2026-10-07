#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分子筛选工作流统一入口。

    python run_workflow.py --demo
    python run_workflow.py --demo --steps qsar admet
    python run_workflow.py --config config/workflow_config.yaml --steps sa viz

每一步都从约定的 CSV 读取、写到下一份 CSV，因此中断后可以用 --steps 从该步继续。
演示模式不训练模型，也不访问网络。
"""

import argparse
import logging
import os
import sys
import time
import traceback
from datetime import datetime

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from admet_engine import run_admet_filter
from config_loader import load_raw_config, resolve_config
from io_utils import read_table
from qsar_engine import qsar_predict_and_filter
from rnn_workflow import run_rnn_generation
from sa_scorer import run_sa_filter
from submit_job_docking import submit_docking_job
from visualizer import generate_plots, generate_summary_report

STEP_ORDER = ("rnn", "qsar", "admet", "docking", "sa", "viz")


class WorkflowLogger:
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"workflow_{timestamp}.log")
        self.logger = logging.getLogger(f"workflow_{timestamp}")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        stream_handler = logging.StreamHandler(sys.stdout)
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)

    def log_step(self, step_name, status, duration=None, output_path=None):
        message = f"[{step_name}] - {status}"
        if duration is not None:
            message += f" (耗时: {duration:.2f}秒)"
        if output_path:
            message += f" -> {output_path}"
        self.logger.info(message)


class MolecularScreeningWorkflow:
    def __init__(self, config):
        self.config = config
        self.logger = WorkflowLogger(config["paths"]["logs_dir"])
        self._prepare_dirs()

    def _prepare_dirs(self):
        for path in self.config["paths"].values():
            parent = path if os.path.splitext(path)[1] == "" else os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        self.logger.log_step("初始化", "目录已就绪")

    def run(self, steps=None):
        selected = list(STEP_ORDER if not steps else [step for step in STEP_ORDER if step in steps])
        self.logger.logger.info("=" * 60)
        mode = "演示" if self.config["demo_mode"] else "正式"
        self.logger.logger.info(f"分子筛选工作流开始（{mode}）步骤: {', '.join(selected)}")
        self.logger.logger.info("=" * 60)
        started = time.time()
        handlers = {
            "rnn": self.run_rnn_generation,
            "qsar": self.run_qsar_prediction,
            "admet": self.run_admet_filter,
            "docking": self.run_docking,
            "sa": self.run_sa_scoring,
            "viz": self.run_visualization,
        }
        try:
            for step in selected:
                handlers[step]()
        except Exception as exc:
            self.logger.logger.error(f"工作流执行失败: {exc}")
            self.logger.logger.error(traceback.format_exc())
            self.logger.logger.error(f"已完成的结果仍保留在 {self.config['paths']['results_dir']}")
            raise
        elapsed = time.time() - started
        self.logger.logger.info("=" * 60)
        self.logger.logger.info(f"工作流执行完成，总耗时 {elapsed:.2f} 秒")
        self.logger.logger.info(f"日志文件: {self.logger.log_file}")
        return self.config["paths"]

    def _timed(self, name, func):
        self.logger.log_step(name, "开始")
        started = time.time()
        try:
            result = func()
        except Exception as exc:
            self.logger.log_step(name, f"失败: {exc}", time.time() - started)
            raise
        self.logger.log_step(name, "完成", time.time() - started)
        return result

    def run_rnn_generation(self):
        def _run():
            run_rnn_generation(self.config, demo_mode=self.config["demo_mode"])
            return self.config["paths"]["generated"]

        return self._timed("RNN分子生成", _run)

    def run_qsar_prediction(self):
        def _run():
            source = self.config["paths"]["generated"]
            qsar_predict_and_filter(
                self.config["qsar_train_data"],
                source,
                self.config["qsar_model"],
                self.config["paths"]["qsar"],
                demo_mode=self.config["demo_mode"],
                top_n=self.config["top_n"],
                ic50_threshold=self.config["ic50_threshold"],
                test_size=self.config["test_size"],
            )
            return self.config["paths"]["qsar"]

        return self._timed("QSAR活性预测", _run)

    def run_admet_filter(self):
        def _run():
            source = self.config["paths"]["qsar"]
            frame = read_table(source)
            run_admet_filter(
                frame,
                criteria=self.config["admet_criteria"],
                output_path=self.config["paths"]["admet"],
            )
            return self.config["paths"]["admet"]

        return self._timed("ADMET性质过滤", _run)

    def run_docking(self):
        def _run():
            try:
                submit_docking_job(
                    self.config["docking_engines"],
                    input_csv=self.config["paths"]["admet"],
                    output_csv=self.config["paths"]["docking"],
                    demo_mode=self.config["demo_mode"],
                    receptor_pdb=self.config["receptor_pdb"],
                    box=self.config["docking_box"],
                )
            except Exception as exc:
                if self.config["demo_mode"]:
                    raise
                self.logger.logger.warning(f"分子对接未产出分数，后续步骤改用 ADMET 结果: {exc}")
            return self.config["paths"]["docking"]

        return self._timed("分子对接", _run)

    def run_sa_scoring(self):
        def _run():
            docking_path = self.config["paths"]["docking"]
            admet_path = self.config["paths"]["admet"]
            source = docking_path if os.path.exists(docking_path) else admet_path
            if source == admet_path:
                self.logger.logger.warning(f"未找到对接结果，SA Score 改用 {admet_path}")
            frame = read_table(source)
            run_sa_filter(
                frame,
                threshold=self.config["sa_threshold"],
                output_path=self.config["paths"]["sa"],
                sort=self.config["sa_sort"],
            )
            return self.config["paths"]["sa"]

        return self._timed("SA Score评估", _run)

    def run_visualization(self):
        def _run():
            source = self.config["paths"]["sa"]
            frame = read_table(source)
            output = self.config["paths"]["plots"]
            generate_plots(frame, output_path=output)
            report = os.path.join(self.config["paths"]["results_dir"], "summary_report.txt")
            generate_summary_report(frame, output_path=report)
            return output

        return self._timed("结果可视化", _run)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="分子筛选工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_workflow.py --demo
  python run_workflow.py --demo --steps rnn qsar
  python run_workflow.py --steps sa viz
        """,
    )
    parser.add_argument("--config", default="config/workflow_config.yaml")
    parser.add_argument("--demo", action="store_true", help="使用 demo/data，不训练、不访问网络")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=STEP_ORDER,
        help="只运行列出的步骤，顺序固定为 rnn qsar admet docking sa viz",
    )
    args = parser.parse_args(argv)

    try:
        raw = load_raw_config(args.config)
        config = resolve_config(raw, demo_mode=args.demo)
    except Exception as exc:
        print(f"无法加载配置: {exc}")
        return 1

    if args.demo:
        print("运行演示模式。QSAR、对接和缺失的 ADMET 列使用占位值。")

    workflow = MolecularScreeningWorkflow(config)
    try:
        workflow.run(args.steps)
    except Exception as exc:
        print(f"\n工作流执行失败: {exc}")
        print(f"查看日志: {workflow.logger.log_file}")
        return 1

    print("\n工作流执行成功")
    print(f"查看日志: {workflow.logger.log_file}")
    for name in ("generated", "qsar", "admet", "docking", "sa", "plots"):
        path = config["paths"][name]
        if os.path.exists(path):
            print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
