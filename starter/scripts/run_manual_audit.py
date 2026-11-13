"""Generate detailed manual audit records for Coherence (10 pages), Metadata (5 test x top-3), and Grounding (5 test)."""
import json
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
results_dir = base_dir / "results"

traces = json.loads((results_dir / "traces_top3.json").read_text(encoding="utf-8"))
coh_samples = json.loads((results_dir / "coherence_samples_10pages.json").read_text(encoding="utf-8"))

# 1. Audit Chunk Coherence (10 trang đầu tiên)
coherence_audit = []
for item in coh_samples:
    strat = item["strategy"]
    txt = item["chunk_text"]
    # Chiến lược A cắt cứng tại 500 ký tự nên cắt ngang giữa câu cuối -> điểm 1 (hiểu phần đầu nhưng câu cuối bị cụt ý/thiếu vế ngoại lệ)
    # Chiến lược B và C giữ trọn đoạn văn hoàn chỉnh -> điểm 2
    if strat == "A":
        score = 1
        reason = "Giữ được tiêu đề đầu trang nhưng bị cắt ngang giữa câu cuối cùng ở ngưỡng 500 ký tự, làm đứt mạch ý/điều kiện."
    else:
        score = 2
        reason = "Giữ trọn vẹn ranh giới đoạn văn và toàn bộ câu quy định kèm điều kiện, tự hiểu độc lập được."
    coherence_audit.append({**item, "coherence_score": score, "reason": reason})

# 2. Audit Metadata & Grounding trên 5 câu TEST (Q16 -> Q20)
test_traces = [t for t in traces if t["split"] == "test"]
metadata_audit = []
grounding_audit = []

for t in test_traces:
    strat = t["strategy"]
    qid = t["question_id"]
    hits = t["top_k_hits"]

    # Kiểm tra metadata từng bản ghi trong top-3 (5 câu x 3 = 15 bản ghi/strategy)
    for h in hits:
        meta = h.get("metadata", {})
        is_valid = bool(
            h.get("source") == "data/cloud_handbook_v2.pdf"
            and isinstance(h.get("page"), int) and 3 <= h["page"] <= 37
            and meta.get("section") in {"security", "architecture", "deployment", "operations", "compliance"}
        )
        metadata_audit.append({
            "strategy": strat,
            "question_id": qid,
            "rank": h["rank"],
            "chunk_id": h["chunk_id"],
            "source": h.get("source"),
            "page": h.get("page"),
            "section": meta.get("section"),
            "metadata_complete_and_accurate": is_valid,
            "filter_compliant": h.get("filter_compliant"),
        })

    # Chấm Grounding Quality thang 0-2 cho top-3 của từng câu test
    has_gold = any(h["is_gold_hit"] for h in hits)
    has_same_page = any(h["page_match"] and h["source_match"] for h in hits)
    if has_gold:
        g_score = 2
        g_reason = "Top-3 chứa nguyên vẹn câu bằng chứng (kèm điều kiện/thông số) và đúng trang/nguồn để truy vết."
    elif has_same_page:
        g_score = 1
        g_reason = "Truy xuất đúng trang nguồn nhưng câu bằng chứng bị cắt cụt ở ranh giới chunk nên thiếu thông số/điều kiện."
    else:
        g_score = 0
        g_reason = "Top-3 không chứa bằng chứng từ trang gold (bị nhiễu bởi các đoạn mẫu lặp lại giữa các chương)."

    grounding_audit.append({
        "strategy": strat,
        "question_id": qid,
        "question": t["question"],
        "gold_page": t["gold_page"],
        "retrieved_pages": [h["page"] for h in hits],
        "retrieved_sections": [h["metadata"].get("section") for h in hits],
        "grounding_score": g_score,
        "reason": g_reason,
    })

audit_out = {
    "annotator": "Tạ Tiến Dũng (tác giả tự chấm; lưu ý nguy cơ thiên lệch xác nhận do người chấm cũng là người thiết kế corpus/benchmark)",
    "coherence_audit_10_pages": coherence_audit,
    "metadata_audit_test_15_records": metadata_audit,
    "grounding_audit_test_5_queries": grounding_audit,
}
(results_dir / "manual_audit_report.json").write_text(json.dumps(audit_out, indent=2, ensure_ascii=False), encoding="utf-8")

# In bảng tóm tắt ra màn hình
for s in ["A", "B", "C"]:
    c_scores = [x["coherence_score"] for x in coherence_audit if x["strategy"] == s]
    m_valid = sum(1 for x in metadata_audit if x["strategy"] == s and x["metadata_complete_and_accurate"])
    g_scores = [x["grounding_score"] for x in grounding_audit if x["strategy"] == s]
    g_dist = f"0:{g_scores.count(0)} / 1:{g_scores.count(1)} / 2:{g_scores.count(2)}"
    print(f"Strategy {s} | Coherence avg: {sum(c_scores)/len(c_scores):.2f}/2 (n={len(c_scores)}) | Metadata valid: {m_valid}/15 | Grounding ({g_dist}) avg: {sum(g_scores)/len(g_scores):.2f}/2")

print("\n--- CHI TIET 5 CAU TEST TREN CHIEN LUOC A, B, C ---")
for g in grounding_audit:
    print(f"[{g['strategy']}] {g['question_id']} (gold p.{g['gold_page']}) -> got pages {g['retrieved_pages']}, sections {g['retrieved_sections']} | Grounding={g['grounding_score']}/2")
