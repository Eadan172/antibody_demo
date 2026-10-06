"""各阶段提示词。要求模型把不确定的公开信息标出来，禁止编造实验和结构分数。"""

SYSTEM = """你是抗体药物早期设计流程中的资料整理与序列设计助手。
规则：
1. 亲和力、表位、特异性、热稳定性、免疫原性都写成「预测」或「设计选择」，不要写成已完成的实验结论。
2. 不要编造 iPTM、pLDDT、PAE、KD 实测值、临床试验编号。没有把握的在研药物写成「公开信息不充分，需复核」。
3. 序列使用标准氨基酸单字母，只给可变区，不要恒定区。
4. 需要 JSON 时，只输出一个 JSON 对象。
"""

SPEC_USER = """阅读下面的抗体设计需求，整理成 JSON。不要设计序列。

需求原文：
<<<
{text}
>>>

已经由程序解析、请原样保留的信息：
- 项目名称：{project}
- 指定靶点：{targets}
- 每路线每靶点候选数：{count}
- 计算软件数量：{tool_count}（地址由程序处理，不要改写）

输出 JSON 字段：
{{
  "task_summary": "一段话概括要做什么",
  "target_mode": "specified 或 discover",
  "target_names": ["若原文指定了靶点就照抄，否则空数组"],
  "n_targets": 3,
  "species": ["种属要求，短句"],
  "physicochemical": ["理化与可开发性要求，短句"],
  "formats": ["分子格式"],
  "modalities": ["功能模态"],
  "extra_constraints": "其他必须遵守的限制"
}}
若原文指定了靶点，target_mode 必须是 specified，target_names 与指定靶点一致。
"""

RESEARCH_USER = """根据需求做靶点调研，输出 JSON。这是文档《00_靶点调研报告》的素材。

需求摘要：
{summary}

模式：{mode}
指定靶点：{targets}
需要的靶点数量：{n_targets}
种属：{species}
理化：{physicochemical}
模态：{modalities}
其他限制：{extra}

若模式是 specified，selected 只能包含指定靶点，不要替换成别的靶点。pool 里可以包含被排除的对照靶点，用来说明为什么指定靶点更合适，但不要求凑数。
若模式是 discover，按「研究热度、上市药物少、结构可设计、有差异化空间」选出 n_targets 个靶点。

输出：
{{
  "method": "调研方法，说明依据来自模型知识截止前的公开信息，不确定处需复核",
  "criteria": ["筛选标准"],
  "pool": [
    {{"name":"", "heat":"", "approved":"", "competition":"", "decision":"入选|排除|备选", "reason":""}}
  ],
  "selected": [
    {{
      "name": "主名称，例如 CDH17",
      "aliases": "别名",
      "uniprot": "有把握才填，否则写未复核",
      "mol_type": "分子类型",
      "expression": "表达谱",
      "approved_drugs": "上市药物情况",
      "pipeline": "在研格局；不确定就写公开信息不充分，需复核",
      "design_points": "抗体设计要点：表位、内化、种属交叉、特异性",
      "differentiation": "差异化空间",
      "risks": "主要脱靶或设计风险",
      "heat": "热度依据",
      "competition": "竞争密度"
    }}
  ],
  "conclusion": "一段结论"
}}
"""

DESIGN_USER = """你负责本次任务中的设计路线「{name}」。它只是一条互补的序列设计策略，不是某个软件或商品的输出。不要使用用户需求里没有出现的商品名、公司名或软件品牌作为路线名或候选前缀。只为下面这一个靶点设计 {batch} 条新候选。

靶点档案：
{dossier}

用户需求：
- 种属：{species}
- 理化：{physicochemical}
- 格式：{formats}
- 模态：{modalities}
- 其他：{extra}
- 本路线侧重点：{focus}

已使用、禁止重复的 CDR-H3：{used_h3}
已使用的 VH 胚系：{used_vh}

输出 JSON：
{{
  "route_overview": "本路线针对该靶点的策略，120字内",
  "target_strategy": "表位怎么分开、格式怎么分配，120字内",
  "candidates": [
    {{
      "epitope": "预测表位，短句",
      "format": "如 IgG1/κ 或 IgG4-S228P/λ 或 scFv-Fc 或 Fab",
      "vh_germline": "如 IGHV3-23*01/JH4",
      "vl_germline": "如 IGKV1-39*01/JK1",
      "vh": "完整 VH",
      "vl": "完整 VL",
      "cdr_h1": "必须是 vh 的子串",
      "cdr_h2": "必须是 vh 的子串",
      "cdr_h3": "必须是 vh 的子串，且与已用 CDR-H3 不同",
      "cdr_l1": "必须是 vl 的子串",
      "cdr_l2": "必须是 vl 的子串",
      "cdr_l3": "必须是 vl 的子串",
      "kd_pred": "预测区间，写成文字，不要假装实测",
      "specificity": "预测的交叉风险",
      "immunogenicity": "预测",
      "aggregation": "预测",
      "tm": "预测趋势，不要给虚假精确实验值",
      "ptm_note": "你注意到的 CDR 风险；没有就写未发现",
      "strategy": "这条候选的差异化",
      "optimization": "下一步序列优化建议",
      "function_score": 7,
      "specificity_score": 7
    }}
  ]
}}

硬性要求：
- VH 长度 110–130，VL 长度 100–125，标准氨基酸。
- CDR 字符串必须能在对应链里原样找到。
- 尽量避免 CDR 中的 N-X-S/T（X 不为 P）。这是用户的可开发性要求。
- 不要输出 iPTM/pLDDT。
- candidates 长度必须等于 {batch}。
"""
