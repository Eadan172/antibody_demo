"""无需额外密钥的 PubMed 公开文献检索。"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search_pubmed(query: str, limit: int = 8, timeout: int = 30) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"db": "pubmed", "term": query, "retmode": "json", "retmax": limit, "sort": "date"}
    )
    search = _get_json(f"{PUBMED_API}/esearch.fcgi?{params}", timeout)
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    summary_params = urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    )
    summary = _get_json(f"{PUBMED_API}/esummary.fcgi?{summary_params}", timeout)
    result = summary.get("result", {})
    records: list[dict[str, Any]] = []
    for pmid in ids:
        item = result.get(pmid, {})
        records.append(
            {
                "pmid": pmid,
                "title": item.get("title", "").rstrip("."),
                "authors": [author.get("name", "") for author in item.get("authors", [])[:6]],
                "journal": item.get("fulljournalname") or item.get("source", ""),
                "date": item.get("pubdate", ""),
                "doi": _find_doi(item.get("articleids", [])),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "query": query,
            }
        )
    return records


def collect_research(queries: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for query in queries:
        try:
            for record in search_pubmed(query):
                if record["pmid"] not in seen:
                    seen.add(record["pmid"])
                    records.append(record)
        except Exception as exc:  # 单个查询失败不应中断完整工作流
            errors.append(f"{query}: {exc}")
    return records, errors


def _get_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "antibody-workflow/2.0 (public-literature-research)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _find_doi(article_ids: list[dict[str, str]]) -> str:
    for article_id in article_ids:
        if article_id.get("idtype") == "doi":
            return article_id.get("value", "")
    return ""
