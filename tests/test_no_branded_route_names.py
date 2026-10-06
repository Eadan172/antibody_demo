"""开源文件里不能出现案例附件中的商品名、公司昵称和对应候选前缀。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "output", "__pycache__", ".pytest_cache"}
# 用拼接避免本测试文件本身包含完整词面
NEEDLES = [
    "博" + "兹",
    "普" + "腾",
    "Bol" + "tz",
    "Proten" + "ix",
    "BL" + "Z-",
    "BL" + "Z_",
    "PR" + "X-",
    "PR" + "X_",
]


def test_repository_does_not_embed_case_study_brands():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".txt", ".sh", ".bat"}:
            continue
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in NEEDLES:
            if needle in text:
                hits.append(f"{path.relative_to(ROOT)}: {needle}")
    assert hits == []
