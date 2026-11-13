"""Pipeline entry point for Day 06 Data Ingestion Engineering."""
import json
import os
import statistics
import time
from pathlib import Path
from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .models import Chunk
from .store import PgVectorStore


def main() -> None:
    load_dotenv()
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    db_url = os.getenv("DATABASE_URL", "local_chroma")
    model_name = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )

    manifest_path = data_dir / "manifest.json"
    benchmark_path = data_dir / "benchmark.json"

    if not manifest_path.exists() or not benchmark_path.exists():
        raise FileNotFoundError(
            "Missing data/manifest.json or data/benchmark.json. "
            "Run `python scripts/generate_corpus_and_benchmark.py` first!"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    questions = benchmark["questions"]

    all_useful_pages = []
    page_lookup: dict[tuple[str, int], str] = {}
    ingestion_errors: list[dict] = []

    for doc in manifest["documents"]:
        pdf_path = base_dir / doc["local_path"]
        pages = load_pdf(
            path=pdf_path,
            document_id=doc["source_id"],
            source=doc["source_path_or_url"],
            extra_metadata={"version": doc.get("version", "1.0")},
        )
        for p in pages:
            page_lookup[(p.document_id, p.page)] = p.text
            if p.metadata.get("is_useful"):
                all_useful_pages.append(p)
            else:
                ingestion_errors.append(
                    {
                        "document_id": p.document_id,
                        "page": p.page,
                        "reason": "Excluded (cover/TOC/empty or <100 chars)",
                        "char_count": p.metadata.get("char_count", 0),
                    }
                )

    if len(all_useful_pages) < 30:
        raise ValueError(f"Corpus only has {len(all_useful_pages)} useful pages (< 30 minimum).")

    print(f"[1/5] Loaded {len(all_useful_pages)} useful pages (excluded {len(ingestion_errors)} non-content pages).")

    for q in questions:
        key = (q["gold_source_id"], int(q["gold_page"]))
        page_text = page_lookup.get(key, "")
        if q["evidence_quote"].lower() not in page_text.lower():
            raise ValueError(f"Evidence check failed for {q['id']} on {key}")
    print(f"[2/5] Verified all {len(questions)} benchmark evidence quotes against normalized pages.")

    embedder = MyEmbedder(model_name=model_name)
    store = PgVectorStore(database_url=db_url, dimensions=embedder.dimensions)
    store.create_schema()
    print(f"[3/5] Connected Embedder ({embedder.model_name}, dim={embedder.dimensions}) & ChromaDB Store.")

    strategy_configs = {
        "A": {"chunker": lambda p: fixed_size(p, size=500, overlap=50), "use_filter": False},
        "B": {"chunker": lambda p: by_paragraph(p, max_size=600), "use_filter": False},
        "C": {"chunker": lambda p: by_paragraph(p, max_size=600), "use_filter": True},
    }

    strategy_stats: dict[str, dict] = {}
    chunks_by_strategy: dict[str, list[Chunk]] = {}

    for strat, cfg in strategy_configs.items():
        t0 = time.perf_counter()
        strat_chunks: list[Chunk] = []
        for page in all_useful_pages:
            strat_chunks.extend(cfg["chunker"](page))

        texts = [c.text for c in strat_chunks]
        vectors = embedder.embed_documents(texts)
        store.upsert(strat, strat_chunks, vectors)
        ingest_sec = round(time.perf_counter() - t0, 3)

        count_before = store.count_chunks(strat)
        store.upsert(strat, strat_chunks, vectors)
        count_after = store.count_chunks(strat)
        assert count_before == count_after, f"Duplicate chunks detected on re-ingest for {strat}!"

        lengths = [len(c.text) for c in strat_chunks]
        chunks_by_strategy[strat] = strat_chunks
        strategy_stats[strat] = {
            "strategy": strat,
            "chunk_count": len(strat_chunks),
            "total_chars": sum(lengths),
            "approx_tokens": sum(len(c.text.split()) for c in strat_chunks),
            "min_len": min(lengths),
            "median_len": int(statistics.median(lengths)),
            "max_len": max(lengths),
            "ingest_time_sec": ingest_sec,
            "cost_usd": 0.0,
            "reingest_idempotent": (count_before == count_after),
        }
        print(f"  -> Strategy {strat}: {len(strat_chunks)} chunks ingested in {ingest_sec}s (idempotent OK).")

    all_traces: list[dict] = []
    for strat, cfg in strategy_configs.items():
        for q in questions:
            q_vec = embedder.embed_query(q["question"])
            active_filter = q.get("filter") if cfg["use_filter"] else None
            hits = store.search(strategy=strat, query_vector=q_vec, top_k=3, filters=active_filter)
            trace = evaluate_query(q, hits)
            trace["strategy"] = strat
            trace["applied_filter"] = active_filter
            all_traces.append(trace)

    metrics_summary = summarize(all_traces)
    print("[4/5] Evaluated all queries across strategies A, B, and C:")
    for k, v in sorted(metrics_summary.items()):
        print(
            f"  {v['strategy']} ({v['split']:4s}) | Hit@1: {v['hit_at_1_fraction']:14s} "
            f"| Hit@3: {v['evidence_hit_at_3_fraction']:14s} | Filter: {v['filter_compliance_fraction']}"
        )

    first_10_pages = sorted(all_useful_pages, key=lambda x: (x.document_id, x.page))[:10]
    coherence_samples = []
    for p in first_10_pages:
        anchor = p.text[:120]
        for strat in ["A", "B", "C"]:
            matching = [c for c in chunks_by_strategy[strat] if c.document_id == p.document_id and c.page == p.page]
            chosen = matching[0] if matching else None
            coherence_samples.append(
                {
                    "page_id": f"{p.document_id}_p{p.page:03d}",
                    "strategy": strat,
                    "chunk_id": chosen.chunk_id if chosen else None,
                    "chunk_text": chosen.text if chosen else "",
                    "anchor_preview": anchor,
                }
            )

    (results_dir / "traces_top3.json").write_text(json.dumps(all_traces, indent=2, ensure_ascii=False), encoding="utf-8")
    (results_dir / "metrics_summary.json").write_text(
        json.dumps({"strategy_stats": strategy_stats, "metrics": metrics_summary}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (results_dir / "ingestion_errors.json").write_text(
        json.dumps(ingestion_errors, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (results_dir / "coherence_samples_10pages.json").write_text(
        json.dumps(coherence_samples, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[5/5] Saved all traces, metrics, and manual evaluation samples to {results_dir}/")


if __name__ == "__main__":
    main()
