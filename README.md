# 抗体候选设计流水线

下载代码后，在项目目录执行一条命令：创建当前文件夹里的 `.venv`、安装依赖，并按需求文本完成靶点调研、双路线设计、可选的本地计算、快筛和报告。

正式使用时只需要准备自己的 LLM API Key。接口如果不是 OpenAI，首次运行时再填 Base URL 和模型名，或事先改 `config.yaml`。

## 一条命令

Linux / macOS：

```bash
git clone https://github.com/Eadan172/antibody_demo.git
cd antibody_demo
chmod +x run.sh
./run.sh
```

Windows：

```bat
run.bat
```

第一次会：

1. 在当前目录创建 `.venv`
2. 安装 `requirements.txt`
3. 提示输入 `LLM API Key`，写入 `.env`（此文件不会被 git 跟踪）
4. 读取 `input/requirements.txt`，把结果写到 `output/日期时间/`

只配置环境、先不跑任务：

```bash
./run.sh --setup-only
```

不调用模型、用占位数据检查能不能写出全套文件：

```bash
./run.sh --demo
```

## 你要改的输入

编辑 `input/requirements.txt`。可以写靶点、种属、理化性质、分子格式、功能模态，以及每条路线每个靶点要几条候选。靶点一栏留空时，由模型按任务筛选。

本地已经装了 Protenix、Boltz 或其他计算程序时，在「计算软件」段落下按这个格式取消注释：

```text
protenix | cli | /opt/protenix/bin/protenix | {program} predict --input {fasta} --out {outdir} |
boltz | api | http://127.0.0.1:8080/predict | |
```

- `cli`：本机可执行文件。命令模板可用 `{program}`、`{fasta}`、`{outdir}`。不写模板时，程序会收到 FASTA 路径和输出目录两个参数。
- `api`：对地址发 POST JSON：`{"tool": "名称", "sequences": [{"id","target","vh","vl",...}]}`。
- 程序把 `results.json` 写到输出目录，或把 JSON 打到标准输出。识别的字段是 `id`、`iptm`、`plddt`、`ptm`、`pae`、`score`。
- 找不到程序、接口失败或结果里没有这些字段时，流程继续，并且在报告里写明没有结构分数。不会编造 iPTM / pLDDT。

## 流程

和一次完整的候选设计记录一样，运行时按这些步骤推进：

1. 要求分析：读入文本，拆成靶点、种属、理化、格式、模态和计算软件
2. 靶点调研：指定靶点就只整理这些靶点；没指定就按「热度、上市药、可设计性」筛选
3. 双路线设计：博兹（Boltz·MSA 风格）和普腾（Protenix·MSA 风格）分批给出可变区
4. 计算：只调用输入文件里写明并且确实能跑通的程序或接口
5. 去冗余：比较 VH / VL / CDR-H3，表位不同的高相似配对不合并
6. 快筛：扫描 CDR 糖基化、脱酰胺、氧化、异构化，糖基化直接过滤并打分
7. 报告汇编

## 输出文件

每次运行的目录里有：

| 文件 | 内容 |
|---|---|
| `工作日志.md` | 这次实际做了哪些阶段 |
| `完成概览.md` | 靶点、候选数量和优先顺序 |
| `00_靶点调研报告.md` | 靶点筛选或核对 |
| `01_博兹_BoltzMSA_抗体设计报告.md` | 博兹路线 |
| `02_普腾_ProtenixMSA_抗体设计报告.md` | 普腾路线 |
| `02b_双路线候选序列索引.md` | 序列索引 |
| `02c_双路线去冗余核对报告.md` | 去冗余 |
| `02d_BLZ_*候选_可变区序列.fasta` | 博兹 FASTA |
| `02e_PRX_*候选_可变区序列.fasta` | 普腾 FASTA |
| `03_候选汇总清单_*条.md` | 汇总表 |
| `04_快筛初筛报告.md` | 逐条 PTM、过滤、打分、下游建议 |
| `05_综合评估报告.md` | 主交付 |
| `06_综合评估报告.html` | 同一份结果的网页版 |

`output/LATEST.txt` 记录最近一次目录。设计阶段的检查点在该目录的 `_state/`。中断后可以对同一目录加 `--resume`，跳过已经完成的模型设计，重新做计算和报告。

## 模型接口

`config.yaml` 的 `llm.base_url` 和 `llm.model` 使用 OpenAI 兼容的 `/chat/completions`。常见写法：

- OpenAI：`https://api.openai.com/v1`，模型如 `gpt-4o-mini`
- DeepSeek：`https://api.deepseek.com`，模型如 `deepseek-chat`
- 通义兼容模式：`https://dashscope.aliyuncs.com/compatible-mode/v1`

密钥只放在 `.env` 的 `LLM_API_KEY`。也可以临时用环境变量覆盖，不写进文件。

## 结果怎么理解

序列、表位、亲和力区间、特异性和热稳定性都是预测或设计选择。快筛分数来自序列规则，不是晶体结构，也不是湿实验。CDR 里出现 `N-X-S/T`（X 不为 P）会被过滤。

## 测试

```bash
./run.sh --demo
.venv/bin/python -m pytest tests/test_requirement_parse.py tests/test_screen_and_dedup.py tests/test_compute_runner.py tests/test_pipeline_demo.py -q
```

## 原来的理化排序示例

`antibody_virtual_screening.py` 仍可用标准库对一批带理化分数的候选做排序，不调用大模型：

```bash
.venv/bin/python antibody_virtual_screening.py
```

## 许可证

MIT License
