"""Evaluate retrieved evidence and preserve per-query traces."""
import re
from typing import Any


def _norm_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _is_evidence_hit(chunk_text: str, evidence_quote: str) -> bool:
    norm_chunk = _norm_for_match(chunk_text)
    norm_ev = _norm_for_match(evidence_quote)
    if not norm_ev:
        return False
    if norm_ev in norm_chunk:
        return True
    ev_words = [w for w in re.findall(r"\w+", norm_ev) if len(w) > 3]
    if len(ev_words) >= 5:
        matched = sum(1 for w in ev_words if w in norm_chunk)
        return (matched / len(ev_words)) >= 0.85
    return False


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and enough gold evidence; keep hit@1 and hit@3 trace."""
    gold_sources = question.get("gold_source_id")
    if isinstance(gold_sources, str):
        gold_sources = [gold_sources]

    gold_pages = question.get("gold_page")
    if isinstance(gold_pages, int):
        gold_pages = [gold_pages]

    ev_quotes = question.get("evidence_quote")
    if isinstance(ev_quotes, str):
        ev_quotes = [ev_quotes]

    req_filter = question.get("filter") or {}

    annotated_hits: list[dict[str, Any]] = []
    hit_ranks: list[int] = []
    filter_compliant_count = 0

    for rank, h in enumerate(hits[:3], start=1):
        h_doc = h.get("document_id") or h.get("metadata", {}).get("document_id")
        h_src = h.get("source") or h.get("metadata", {}).get("source")
        h_page = h.get("page") or h.get("metadata", {}).get("page")
        h_text = h.get("text", "")
        h_meta = h.get("metadata", {})

        source_ok = (h_doc in gold_sources) or (h_src in gold_sources)
        page_ok = h_page in gold_pages
        ev_ok = any(_is_evidence_hit(h_text, eq) for eq in ev_quotes)
        is_hit = bool(source_ok and page_ok and ev_ok)

        filter_ok = True
        for fk, fv in req_filter.items():
            if str(h_meta.get(fk)) != str(fv):
                filter_ok = False
                break
        if filter_ok:
            filter_compliant_count += 1

        if is_hit:
            hit_ranks.append(rank)

        annotated_hits.append(
            {
                **h,
                "rank": rank,
                "source_match": source_ok,
                "page_match": page_ok,
                "evidence_match": ev_ok,
                "is_gold_hit": is_hit,
                "filter_compliant": filter_ok,
            }
        )

    hit_at_1 = 1 if (1 in hit_ranks) else 0
    hit_at_3 = 1 if len(hit_ranks) > 0 else 0
    has_filter = len(req_filter) > 0
    top3_filter_pass = (filter_compliant_count == len(annotated_hits)) and len(annotated_hits) > 0

    return {
        "question_id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question.get("expected_answer"),
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "filter": req_filter if has_filter else None,
        "hit_at_1": hit_at_1,
        "evidence_hit_at_3": hit_at_3,
        "has_filter": has_filter,
        "top3_filter_compliant": top3_filter_pass if has_filter else None,
        "top_k_hits": annotated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    summary: dict[str, dict[str, Any]] = {}

    for t in traces:
        strat = t.get("strategy", "unknown")
        split = t.get("split", "unknown")
        key = f"{strat}__{split}"
        if key not in summary:
            summary[key] = {
                "strategy": strat,
                "split": split,
                "total": 0,
                "hit_at_1_count": 0,
                "hit_at_3_count": 0,
                "filter_questions": 0,
                "filter_compliant_questions": 0,
            }
        bucket = summary[key]
        bucket["total"] += 1
        bucket["hit_at_1_count"] += int(t.get("hit_at_1", 0))
        bucket["hit_at_3_count"] += int(t.get("evidence_hit_at_3", 0))
        if t.get("has_filter"):
            bucket["filter_questions"] += 1
            if t.get("top3_filter_compliant"):
                bucket["filter_compliant_questions"] += 1

    for key, b in summary.items():
        n = b["total"]
        h1 = b["hit_at_1_count"]
        h3 = b["hit_at_3_count"]
        fq = b["filter_questions"]
        fc = b["filter_compliant_questions"]
        b["hit_at_1_fraction"] = f"{h1}/{n} ({(h1/n*100):.1f}%)" if n else "0/0"
        b["evidence_hit_at_3_fraction"] = f"{h3}/{n} ({(h3/n*100):.1f}%)" if n else "0/0"
        b["filter_compliance_fraction"] = f"{fc}/{fq} ({(fc/fq*100):.1f}%)" if fq > 0 else "N/A"

    return summary
