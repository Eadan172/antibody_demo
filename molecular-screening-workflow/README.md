# 分子筛选工作流 (Molecular Screening Workflow)

端到端的分子筛选流程：RNN 生成、QSAR、ADMET、对接、SA Score、可视化。各步通过约定的 CSV 交接，可以整段运行，也可以从中断的步骤继续。

## 当前可运行范围

`python run_workflow.py --demo` 使用 `demo/data/` 里的小表跑完六步。演示模式不训练模型，不访问网络。QSAR 活性、对接结合能，以及输入里缺失的 ADMET 列，都是可复现的占位值，不是模型预测。

正式生成和正式 QSAR 预测需要先单独训练。训练不会在生成失败时自动开始。

```bash
python src/rnn_workflow.py --train
python src/qsar_engine.py --train
python run_workflow.py
```

在线对接还需要受体 PDB 和环境变量 `NEUROSNAP_API_KEY`。当前版本只提交任务，不取回结合能。

## 环境

- Python 3.8+
- 演示模式：`pandas`、`pyyaml`
- 真实 SA Score、描述符和 3D 结构：RDKit（建议用 conda 安装）
- 训练 RNN：TensorFlow、SELFIES、RDKit
- 训练 QSAR：scikit-learn、RDKit

```bash
git clone https://github.com/Eadan172/molecular-screening-workflow.git
cd molecular-screening-workflow
pip install pandas pyyaml
python run_workflow.py --demo
```

## 用法

```bash
# 演示模式，六步都跑
python run_workflow.py --demo

# 只跑其中几步。顺序固定，每步读取上一步留下的 CSV
python run_workflow.py --demo --steps qsar admet

# 使用配置文件。嵌套字段会传到对应步骤
python run_workflow.py --config config/workflow_config.yaml
```

`config/workflow_config.yaml` 里实际生效的项包括：生成数量、IC50 阈值、`top_n`、ADMET 过滤值、对接引擎名、受体路径、对接盒、SA 阈值，以及下面这些输出路径。

| 步骤 | 输出 |
| --- | --- |
| RNN | `results/01_generated.csv` |
| QSAR | `results/02_qsar.csv` |
| ADMET | `results/03_admet.csv` |
| 对接 | `results/04_docking.csv` |
| SA Score | `results/05_sa.csv` |
| 可视化 | `results/evaluation_summary.png` |

某一步失败时，已经写好的文件会保留。下一次用 `--steps` 从该步继续。

## 演示数据

`demo/data/sample_molecules.csv` 是待筛选 SMILES。`demo/data/sample_training.csv` 带有 `SMILES`、`IC50`、`IC50_unit`，其中的活性数字是占位标签，不是实验测定值。

```bash
bash demo/run_demo.sh
```

`data/` 下体积较大的表目前是 Git LFS 指针文本，仓库里没有对应的 `.gitattributes`。演示流程不读取这些文件。

## 目录

```
run_workflow.py              # 统一入口
config/workflow_config.yaml
src/rnn_workflow.py          # 生成；--train 才训练
src/qsar_engine.py           # 预测；--train 才训练
src/admet_engine.py
src/submit_job_docking.py
src/sa_scorer.py
src/visualizer.py
demo/data/                   # 演示用小表
```

`src/main_func.py`、`src/rnn-workflow.py`、`src/predict_and_filter.py` 只是转到上面的入口。

## 许可证

MIT，见 [LICENSE](LICENSE)。
