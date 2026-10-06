# 抗体发现自动化工作流

把自然语言抗体需求写进一个文本文件，系统会自动完成需求拆解、PubMed 调研、
候选设计、可选本地/API 计算、结果分析和 00–06 号报告整理。

## 一键运行

Linux / macOS：

```bash
git clone https://github.com/Eadan172/antibody_demo.git
cd antibody_demo
./run.sh examples/抗体需求示例.txt
```

Windows：

```bat
git clone https://github.com/Eadan172/antibody_demo.git
cd antibody_demo
run.bat examples\抗体需求示例.txt
```

首次运行会在当前目录创建 `.venv`，并提示输入 LLM API Key。Key 只写入本地
`.env`（Git 已忽略），之后无需重复输入。核心工作流仅使用 Python 标准库。

默认使用 OpenAI 兼容接口。其他兼容服务可在首次运行前设置：

```bash
export LLM_BASE_URL=https://your-provider.example/v1
export LLM_MODEL=your-model
./run.sh examples/抗体需求示例.txt
```

也可以直接编辑本地 `.env`：

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5-mini
```

## 输入文件

最简单的输入文件可以只有自然语言：

```text
请针对 CLDN6 设计 6 条全人源候选抗体，优先卵巢癌 ADC。
要求区分 CLDN9，检查 PTM，并给出人/食蟹猴种属验证计划。
```

若需指定项目名、检索式或计算软件，可在正文前加入配置块：

```ini
---config
[project]
name = my-project
output_dir = outputs
research_queries =
    CLDN6 antibody cancer
    CLDN6 CLDN9 cross-reactivity

[local_tool:boltz]
command = /opt/boltz/bin/boltz predict --input {input} --out_dir {output_dir}
timeout = 7200

[api_tool:structure_service]
url = https://example.org/api/predict
method = POST
header_authorization = Bearer ${STRUCTURE_API_KEY}
---end

这里开始写完整的抗体要求……
```

本地命令支持三个占位符：

- `{input}`：需求文件绝对路径
- `{output_dir}`：本次运行的 `computations/` 目录
- `{project_dir}`：代码仓库目录

本地工具以参数数组直接执行，不经过 shell。API 工具收到包含需求、需求分析和候选
清单的 JSON。工具的 stdout、stderr、原始响应和执行状态都会留档。

## 输出

每次运行创建独立时间戳目录：

```text
outputs/<项目名>-<时间>/
├── 00_需求分析与任务拆解.md
├── 01_靶点调研报告.md
├── 02_候选设计报告.md
├── 02b_候选可变区序列.fasta
├── 03_候选汇总清单.md
├── 04_计算与快筛报告.md
├── 05_综合评估报告.md
├── 06_综合评估报告.html
├── overview.md
├── run_manifest.json
├── computations/                 # 本地/API 工具原始结果与清单
└── raw/                          # 每个 LLM 阶段的原始 JSON
```

## 证据边界

- PubMed 记录由 NCBI E-utilities 实时检索，并保留 PMID 链接。
- LLM 生成的候选序列只标记为“未验证设计序列”。
- 未配置或未成功运行计算软件时，报告必须写“未计算”，不会生成虚假
  iPTM、pLDDT、KD、结合能或实验数据。
- 输出是研究决策辅助材料，不能替代结构计算、体外实验、动物实验或临床判断。

## 测试与旧版兼容

```bash
python -m unittest discover -s tests -v
```

原有 `antibody_virtual_screening.py` 的数据模型、筛选函数和报告函数继续保留，已有
调用方无需迁移。

## 许可证

MIT
