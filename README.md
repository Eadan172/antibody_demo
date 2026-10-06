# antibody-workflow

从一份抗体需求文本开始，整理出调研、候选设计、计算记录和最终报告。

这个项目原来只是一个理化指标筛选 Demo。后来实际做项目时发现，真正费时间的往往
不是最后那一步排序，而是前面的需求拆解、资料核对，以及把不同软件的结果收拢到一起。
所以在保留旧筛选脚本的同时，补了一套可以从头跑到尾的命令行工作流。

```text
需求文件
   │
   ├── 需求拆解
   ├── PubMed 检索
   ├── 候选设计
   ├── 本地程序 / API 计算（可选）
   └── 快筛、汇总与报告
```

> 这不是“一键得到可用抗体”的黑盒。没有实际运行过的计算会写成“未计算”，
> 模型生成的序列也只会标记为“未验证设计序列”。

## 快速开始

需要 Python 3.10 或更新版本。运行时不依赖第三方 Python 包。

### Linux / macOS

```bash
git clone https://github.com/Eadan172/antibody_demo.git
cd antibody_demo
./run.sh examples/抗体需求示例.txt
```

### Windows

```bat
git clone https://github.com/Eadan172/antibody_demo.git
cd antibody_demo
run.bat examples\抗体需求示例.txt
```

第一次运行会：

1. 在项目目录创建 `.venv`；
2. 询问 LLM API Key；
3. 将 Key 保存到本机 `.env`；
4. 开始处理需求文件。

`.env` 已加入 `.gitignore`，不会随代码提交。之后再次运行时不会重复询问。

默认配置使用 OpenAI 兼容接口：

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5-mini
```

如果使用其他兼容服务，修改 `.env` 中的接口地址和模型名即可。

## 怎么写需求

只有自然语言也能运行。例如：

```text
请针对目标蛋白设计 6 条全人源候选抗体，优先考虑 ADC。

要求：
- 覆盖两个不同胞外表位；
- 检查近缘蛋白交叉反应；
- 目标种属为人和食蟹猴；
- 检查 CDR 区 PTM 与聚集风险；
- 没有真实计算结果时，不要给出结构分数或亲和力数值。
```

示例文件在 [`examples/抗体需求示例.txt`](examples/抗体需求示例.txt)。

### 需要接计算软件时

在正文前加一段配置。下面的路径只是占位，替换成自己机器上的实际命令：

```ini
---config
[project]
name = my-antibody-project
output_dir = outputs
research_queries =
    target antibody cancer
    target homolog cross-reactivity

[local_tool:structure_predictor]
command = /path/to/predictor predict --input {input} --out_dir {output_dir}
timeout = 7200
---end

这里开始写抗体需求……
```

命令里可以使用：

| 占位符 | 实际内容 |
|---|---|
| `{input}` | 需求文件的绝对路径 |
| `{output_dir}` | 本次运行的 `computations/` 目录 |
| `{project_dir}` | 代码仓库目录 |

本地程序不会经过 shell 拼接执行。stdout、stderr、返回码都会保留，方便事后排查。

### 使用 HTTP 计算接口

```ini
[api_tool:structure_service]
url = https://example.org/api/predict
method = POST
timeout = 1800
header_authorization = Bearer ${STRUCTURE_API_KEY}
```

接口会收到需求、需求分析和候选清单组成的 JSON。响应原文会存入本次运行目录。
额外密钥建议放进环境变量，不要直接写在需求文件里。

## 会生成什么

每次运行使用单独的时间戳目录，不会覆盖前一次结果：

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
├── computations/
└── raw/
```

平时先看 `overview.md` 和 `05_综合评估报告.md` 即可。需要追查某条结论时，再去：

- `raw/` 查看各阶段的原始 JSON；
- `computations/` 查看计算程序原始输出；
- `run_manifest.json` 查看本次使用的模型、接口和任务文件。

API Key 不会写入运行清单。

## 结果可信度

工作流刻意把信息分成四类：

| 类型 | 处理方式 |
|---|---|
| 公开资料 | 来自实时 PubMed 检索，保留 PMID 链接 |
| 模型推断 | 明确写成预测、假设或待核验 |
| 计算结果 | 只采用成功执行的本地程序或 API 返回值 |
| 实验结论 | 本项目不生成，只提供后续验证建议 |

如果检索不到足够资料，报告会留下证据缺口；如果计算程序没有安装，流程仍可完成，
但对应部分不会假装已经算过。

## 项目结构

```text
antibody_workflow/
├── config.py       # 任务文件和 .env
├── llm.py          # OpenAI 兼容接口
├── research.py     # PubMed 检索
├── tools.py        # 本地命令与 HTTP API
├── pipeline.py     # 主流程
└── reporting.py    # Markdown / HTML 输出
```

旧版快速筛选逻辑仍在 `antibody_virtual_screening.py`，已有调用不需要迁移。

## 测试

新工作流：

```bash
python -m unittest discover -s tests -v
```

旧版兼容测试：

```bash
cd tests
python test_data_loader.py
python test_screening.py
python test_report.py
```

## 已知限制

- 文献检索目前只接了 PubMed；
- LLM 服务需要兼容 `/chat/completions` 接口；
- 不同计算软件的输入格式差异很大，目前通过命令或 HTTP 适配，没有内置专用转换器；
- 生成序列只能作为下一轮计算和实验的起点。

## License

[MIT](LICENSE)
