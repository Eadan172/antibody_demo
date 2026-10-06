"""命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from antibody_pipeline.envfile import load_env_file, upsert_env


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_llm_defaults(root: Path) -> tuple[str, str]:
    path = root / "config.yaml"
    base_url = "https://api.openai.com/v1"
    model = "gpt-4o-mini"
    if not path.is_file():
        return base_url, model
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        llm = data.get("llm") or {}
        return str(llm.get("base_url") or base_url), str(llm.get("model") or model)
    except Exception:
        return base_url, model


def ensure_api_key(root: Path, interactive: bool) -> None:
    env_path = root / ".env"
    load_env_file(env_path)
    key = os.environ.get("LLM_API_KEY", "").strip()
    if key and key != "your-api-key-here":
        return
    if not interactive or not sys.stdin.isatty():
        raise SystemExit(
            "还没有 LLM API Key。请在项目目录执行 ./run.sh，按提示输入；"
            "或事先写入 .env 的 LLM_API_KEY。只想检查输出文件可加 --demo。"
        )
    default_url, default_model = _config_llm_defaults(root)
    print("请输入 LLM API Key。密钥只写到当前目录的 .env。")
    entered = input("LLM API Key: ").strip()
    if not entered:
        raise SystemExit("未输入 API Key，已停止。")
    updates = {"LLM_API_KEY": entered}
    print(f"接口地址直接回车表示使用 {default_url}")
    typed_url = input("LLM Base URL: ").strip()
    if typed_url:
        updates["LLM_BASE_URL"] = typed_url
        os.environ["LLM_BASE_URL"] = typed_url
    print(f"模型名直接回车表示使用 {default_model}")
    typed_model = input("LLM Model: ").strip()
    if typed_model:
        updates["LLM_MODEL"] = typed_model
        os.environ["LLM_MODEL"] = typed_model
    upsert_env(env_path, updates)
    os.environ["LLM_API_KEY"] = entered
    print(f"已写入 {env_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="读取抗体需求文本，完成调研、设计、可选本地计算、快筛和报告。",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="input/requirements.txt",
        help="需求文本，默认 input/requirements.txt",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="输出目录。默认 output/日期时间",
    )
    parser.add_argument("--demo", action="store_true", help="不调用大模型，用占位数据写出全套文件")
    parser.add_argument("--resume", action="store_true", help="若输出目录已有检查点，跳过设计直接重跑计算和报告")
    parser.add_argument("--n", type=int, default=0, help="覆盖每路线每靶点的候选数，1–12")
    parser.add_argument("--base-url", default="", help="临时覆盖 OpenAI 兼容接口地址")
    parser.add_argument("--model", default="", help="临时覆盖模型名")
    parser.add_argument("--setup-only", action="store_true", help="只检查密钥并确认环境，不跑任务")
    parser.add_argument("--config", default="config.yaml", help="配置文件")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = project_root()
    os.chdir(root)
    if args.n and not 1 <= args.n <= 12:
        print("`--n` 需要在 1 到 12 之间。", file=sys.stderr)
        return 2
    if not args.demo:
        ensure_api_key(root, interactive=True)
    if args.setup_only:
        if args.demo:
            print("演示模式不需要 API Key。环境可运行。")
        else:
            print("API Key 已就绪。去掉 --setup-only 后会按 input/requirements.txt 开始任务。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(args.output) if args.output else root / "output" / stamp
    if not output.is_absolute():
        output = root / output
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    if not args.demo and not input_path.is_file():
        print(f"找不到需求文件：{input_path}", file=sys.stderr)
        return 2

    from antibody_pipeline.pipeline import run_pipeline

    run_pipeline(
        input_path=input_path,
        output_dir=output,
        config_path=root / args.config,
        demo=args.demo,
        resume=args.resume,
        n_override=args.n or None,
        base_url=args.base_url,
        model=args.model,
        project_root=root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
