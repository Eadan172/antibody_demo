"""离线演示数据。用来检查环境能否写出全套文件，不代表真实设计。"""

from __future__ import annotations

from antibody_pipeline.models import Candidate, RequirementSpec, ResearchPack, TargetDossier

_VH3_PREFIX = (
    "EVQLLESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGR"
    "FTISRDNSKNTLYLQMNSLRAEDTAVYYCAK"
)
_VH1_PREFIX = (
    "QVQLVQSGAEVKKPGSSVKVSCKASGGTFSSYAISWVRQAPGQGLEWMGGIIPIFGTANYAQKFQGR"
    "VTITADESTSTAYMELSSLRSEDTAVYYCAR"
)
_VH_SUFFIX = "WGQGTLVTVSS"
_VL1_PREFIX = (
    "DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTD"
    "FTLTISSLQPEDFATYYC"
)
_VL3_PREFIX = (
    "EIVLTQSPGTLSLSPGERATLSCRASQSVSSSYLAWYQQKPGQAPRLLIYGASSRATGIPDRFSGSGSGTD"
    "FTLTISRLEPEDFAVYYC"
)
_VL_SUFFIX = "FGQGTKVEIK"


def _vh(kind: str, h3: str) -> str:
    prefix = _VH3_PREFIX if kind == "vh3" else _VH1_PREFIX
    return prefix + h3 + _VH_SUFFIX


def _vl(kind: str, l3: str) -> str:
    prefix = _VL1_PREFIX if kind == "vl1" else _VL3_PREFIX
    return prefix + l3 + _VL_SUFFIX


def _candidate(**kwargs) -> Candidate:
    kind_h = kwargs.pop("vh_kind")
    kind_l = kwargs.pop("vl_kind")
    h3 = kwargs["cdr_h3"]
    l3 = kwargs["cdr_l3"]
    kwargs["vh"] = _vh(kind_h, h3)
    kwargs["vl"] = _vl(kind_l, l3)
    kwargs.setdefault("source", "demo")
    if kind_h == "vh3":
        kwargs.setdefault("cdr_h1", "SYAMS")
        kwargs.setdefault("cdr_h2", "AISGSGGST")
        kwargs.setdefault("vh_germline", "IGHV3-23*01/JH4")
    else:
        kwargs.setdefault("cdr_h1", "SYAIS")
        kwargs.setdefault("cdr_h2", "GIIPIFGTANYAQKFQG")
        kwargs.setdefault("vh_germline", "IGHV1-69*01/JH4")
    if kind_l == "vl1":
        kwargs.setdefault("cdr_l1", "QSISSYLN")
        kwargs.setdefault("cdr_l2", "AASSLQS")
        kwargs.setdefault("vl_germline", "IGKV1-39*01/JK1")
    else:
        kwargs.setdefault("cdr_l1", "QSVSSSYLA")
        kwargs.setdefault("cdr_l2", "GASSRAT")
        kwargs.setdefault("vl_germline", "IGKV3-20*01/JK1")
    return Candidate(**kwargs)


def build_demo(n_per_route: int = 2):
    her2 = TargetDossier(
        name="HER2",
        aliases="ERBB2（演示）",
        uniprot="P04626",
        mol_type="受体酪氨酸激酶，演示档案",
        expression="演示数据，不作为文献结论",
        approved_drugs="演示：此处不引用具体商业管线",
        pipeline="公开信息不在演示中展开",
        design_points="演示用：远膜阻断与近膜内化两条表位假设",
        differentiation="仅用于走通文件流程",
        risks="与 EGFR 家族的交叉需要真实项目里单独论证",
        heat="演示",
        competition="演示",
        slug="HER2",
    )
    egfr = TargetDossier(
        name="EGFR",
        aliases="ERBB1（演示）",
        uniprot="P00533",
        mol_type="受体酪氨酸激酶，演示档案",
        expression="演示数据，不作为文献结论",
        approved_drugs="演示",
        pipeline="公开信息不在演示中展开",
        design_points="演示用：III 域与近膜表位假设",
        differentiation="仅用于走通文件流程",
        risks="演示",
        heat="演示",
        competition="演示",
        slug="EGFR",
    )
    shared_l3 = "QQSYSTPYT"
    rows = [
        _candidate(
            id="A-HER2-01", route="路线A", route_label="A", expert="路线A", target="HER2",
            epitope="远膜端阻断", format="IgG1/κ", vh_kind="vh1", vl_kind="vl1",
            cdr_h3="GYSSGWYFDY", cdr_l3=shared_l3, kd_pred="预测 1–20 nM",
            specificity="演示：家族交叉风险中低", immunogenicity="低-中（预测）",
            aggregation="低-中（预测）",             tm="中高（预测）", ptm_note="框架含 M，CDR 未故意引入糖基化",
            strategy="演示：阻断格式", optimization="先做序列规则复核",
            function_score=8, specificity_score=7,
        ),
        _candidate(
            id="A-HER2-02", route="路线A", route_label="A", expert="路线A", target="HER2",
            epitope="EC 近膜内化", format="IgG1/κ", vh_kind="vh3", vl_kind="vl1",
            cdr_h3="DREGYYFDY", cdr_l3="QQYNYSPWT", kd_pred="预测 5–50 nM",
            specificity="演示", immunogenicity="中（预测）", aggregation="中（预测）",
            tm="中（预测）", ptm_note="设计时漏看 L3",
            strategy="演示：这条故意留了 CDR 糖基化，用来展示过滤",
            optimization="N→Q 后重筛", function_score=5, specificity_score=6,
        ),
        _candidate(
            id="A-EGFR-01", route="路线A", route_label="A", expert="路线A", target="EGFR",
            epitope="III 域", format="IgG4-S228P/κ", vh_kind="vh3", vl_kind="vl3",
            cdr_h3="GSSGWYFDY", cdr_l3="QQYGSSPYT", kd_pred="预测 2–30 nM",
            specificity="演示", immunogenicity="低（预测）", aggregation="低（预测）",
            tm="中高（预测）", ptm_note="未发现 N-糖基化",
            strategy="演示：低效应格式", optimization="核对同源受体",
            function_score=7, specificity_score=7,
        ),
        _candidate(
            id="A-EGFR-02", route="路线A", route_label="A", expert="路线A", target="EGFR",
            epitope="近膜", format="Fab/κ", vh_kind="vh1", vl_kind="vl3",
            cdr_h3="DLWGGYYFDY", cdr_l3="QQYDNLPYT", kd_pred="预测 5–40 nM",
            specificity="演示", immunogenicity="低-中（预测）", aggregation="中（预测）",
            tm="中（预测）", ptm_note="H3 偏长需看聚集",
            strategy="演示：Fab", optimization="表达后看聚集",
            function_score=6, specificity_score=6,
        ),
        _candidate(
            id="B-HER2-01", route="路线B", route_label="B", expert="路线B", target="HER2",
            epitope="近膜端内化", format="IgG1/κ", vh_kind="vh3", vl_kind="vl1",
            cdr_h3="AREGYYSYFDY", cdr_l3=shared_l3, kd_pred="预测 1–10 nM",
            specificity="演示：与路线A远膜候选表位不同", immunogenicity="低（预测）",
            aggregation="低（预测）", tm="中高（预测）", ptm_note="H1 含 M",
            strategy="演示：与 A-HER2-01 共用轻链框架但表位假设不同",
            optimization="不要与远膜候选合并", function_score=8, specificity_score=6,
        ),
        _candidate(
            id="B-HER2-02", route="路线B", route_label="B", expert="路线B", target="HER2",
            epitope="二聚界面", format="IgG1/κ", vh_kind="vh1", vl_kind="vl3",
            cdr_h3="GGSYFDY", cdr_l3="QQRSNWPYT", kd_pred="预测 1–15 nM",
            specificity="演示", immunogenicity="低-中（预测）", aggregation="低（预测）",
            tm="中高（预测）", ptm_note="未发现 N-糖基化",
            strategy="演示：二聚界面", optimization="做受体二聚实验设计",
            function_score=7, specificity_score=7,
        ),
        _candidate(
            id="B-EGFR-01", route="路线B", route_label="B", expert="路线B", target="EGFR",
            epitope="III 域侧翼", format="scFv-Fc", vh_kind="vh3", vl_kind="vl1",
            cdr_h3="EGYYDSSGYYFDY", cdr_l3="QQANSFPLT", kd_pred="预测 3–30 nM",
            specificity="演示", immunogenicity="低（预测）", aggregation="scFv 需验证",
            tm="中（预测）", ptm_note="H3 含 DS",
            strategy="演示：较小格式", optimization="先看 scFv 聚集",
            function_score=6, specificity_score=6,
        ),
        _candidate(
            id="B-EGFR-02", route="路线B", route_label="B", expert="路线B", target="EGFR",
            epitope="近膜 ADC", format="IgG1/κ", vh_kind="vh1", vl_kind="vl3",
            cdr_h3="DYSYGGYYFDY", cdr_l3="QQYYSTPYT", kd_pred="预测 1–20 nM",
            specificity="演示", immunogenicity="低-中（预测）", aggregation="低-中（预测）",
            tm="中高（预测）", ptm_note="未发现 N-糖基化",
            strategy="演示：内化格式", optimization="内化实验设计",
            function_score=8, specificity_score=7,
        ),
    ]
    # 演示固定 2×2×2。若用户把数量调小，截断到每路线每靶点 n 条。
    if n_per_route < 2:
        kept = []
        seen = {}
        for item in rows:
            key = (item.route_label, item.target)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= n_per_route:
                kept.append(item)
        rows = kept
    spec = RequirementSpec(
        project_name="抗体候选设计（离线演示）",
        task_summary="演示要求分析、双路线设计、去冗余、快筛和报告汇编。这些靶点和序列不是本次调研结论。",
        target_mode="specified",
        target_names=["HER2", "EGFR"],
        n_targets=2,
        species=["人源（演示）"],
        physicochemical=["避免 CDR 区 N-糖基化"],
        formats=["IgG1", "IgG4", "scFv-Fc", "Fab"],
        modalities=["阻断", "内化"],
        n_per_route_per_target=n_per_route if n_per_route < 2 else 2,
        extra_constraints="演示模式不调用大模型",
        raw_text="demo",
        compute_tools=[],
    )
    pack = ResearchPack(
        method="离线演示不访问文献。正式运行会按需求文件调用大模型整理靶点。",
        criteria=["演示用占位标准"],
        pool=[
            {"name": "HER2", "heat": "演示", "approved": "不在演示中展开", "competition": "演示", "decision": "入选", "reason": "用来生成文件"},
            {"name": "EGFR", "heat": "演示", "approved": "不在演示中展开", "competition": "演示", "decision": "入选", "reason": "用来生成文件"},
        ],
        selected=[her2, egfr],
        conclusion="演示流程已选定两个占位靶点，正式任务请去掉 --demo。",
    )
    notes = {
        "route_a": "演示：路线A侧重内化与格式多样性。",
        "route_b": "演示：路线B侧重表位分开，并与路线A共用一条轻链以展示去冗余。",
    }
    strategies = {
        "route_a:HER2": "演示策略：一条阻断，一条带糖基化缺陷以便过滤。",
        "route_a:EGFR": "演示策略：IgG4 与 Fab。",
        "route_b:HER2": "演示策略：近膜与二聚界面，轻链与路线A有一对趋同。",
        "route_b:EGFR": "演示策略：scFv-Fc 与 IgG1。",
    }
    return spec, pack, rows, notes, strategies
