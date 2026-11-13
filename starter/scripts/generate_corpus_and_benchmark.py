"""Generate a valid 37-page PDF (35 useful content pages + cover + TOC), manifest.json, and benchmark.json."""
import datetime
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SECTIONS = ["security", "architecture", "deployment", "operations", "compliance"]

FACTS = [
    # DEV (15 câu: Q01 -> Q15)
    ("Q01", "dev", 1, "security", "direct", "What is the maximum lifetime of an access token in the Cloud Platform?",
     "Access tokens expire strictly after 45 minutes, except for automated batch workers which may request a 120-minute lease.",
     "Access tokens expire strictly after 45 minutes, except for automated batch workers which may request a 120-minute lease.", None),
    ("Q02", "dev", 2, "security", "paraphrase", "How often do master encryption keys need to be rotated?",
     "All master key material in the vault must undergo automatic cryptographic rotation every 90 calendar days.",
     "All master key material in the vault must undergo automatic cryptographic rotation every 90 calendar days.", None),
    ("Q03", "dev", 3, "security", "conditional", "Under what condition is SSH root login permitted on bastion nodes?",
     "Direct SSH root login is strictly prohibited on all bastion nodes unless break-glass emergency mode is activated by two security officers.",
     "Direct SSH root login is strictly prohibited on all bastion nodes unless break-glass emergency mode is activated by two security officers.", None),
    ("Q04", "dev", 4, "security", "filter", "According to the security section, what is the default timeout threshold for external gateway requests?",
     "In the security gateway layer, the default request timeout threshold is configured to 12 seconds per upstream call.",
     "In the security gateway layer, the default request timeout threshold is configured to 12 seconds per upstream call.", {"section": "security"}),
    ("Q05", "dev", 8, "architecture", "direct", "What is the maximum payload size allowed on the internal Kafka event bus?",
     "Messages published to the internal Kafka event bus must not exceed 4 megabytes after compression.",
     "Messages published to the internal Kafka event bus must not exceed 4 megabytes after compression.", None),
    ("Q06", "dev", 9, "architecture", "paraphrase", "How many read replicas are provisioned for each primary PostgreSQL shard?",
     "Each primary PostgreSQL database shard is paired with 3 synchronous and asynchronous read replicas across availability zones.",
     "Each primary PostgreSQL database shard is paired with 3 synchronous and asynchronous read replicas across availability zones.", None),
    ("Q07", "dev", 10, "architecture", "conditional", "When does the API gateway bypass the Redis distributed cache?",
     "The API gateway serves responses from Redis cache by default, except when the client header X-Bypass-Cache is signed by an internal service.",
     "The API gateway serves responses from Redis cache by default, except when the client header X-Bypass-Cache is signed by an internal service.", None),
    ("Q08", "dev", 15, "deployment", "filter", "In the deployment section, what is the default timeout threshold for health checks during rollout?",
     "During canary deployment rollouts, the default request timeout threshold for container readiness probes is 40 seconds.",
     "During canary deployment rollouts, the default request timeout threshold for container readiness probes is 40 seconds.", {"section": "deployment"}),
    ("Q09", "dev", 16, "deployment", "direct", "What error percentage triggers an automatic rollback during a canary release?",
     "An automatic canary rollback is triggered immediately if the HTTP 5xx error rate exceeds 1.5 percent over a 5-minute window.",
     "An automatic canary rollback is triggered immediately if the HTTP 5xx error rate exceeds 1.5 percent over a 5-minute window.", None),
    ("Q10", "dev", 17, "deployment", "paraphrase", "How long are deprecated container images kept in the registry before garbage collection?",
     "Deprecated Docker container images are retained in the private registry for 60 days prior to automated garbage collection.",
     "Deprecated Docker container images are retained in the private registry for 60 days prior to automated garbage collection.", None),
    ("Q11", "dev", 22, "operations", "direct", "What is the maximum acknowledgement time for a Severity-1 incident page?",
     "On-call engineers must acknowledge any Severity-1 pager alert within 10 minutes of dispatch.",
     "On-call engineers must acknowledge any Severity-1 pager alert within 10 minutes of dispatch.", None),
    ("Q12", "dev", 23, "operations", "conditional", "When are database schema migrations allowed during peak business hours?",
     "Production database schema migrations are blocked between 08:00 and 20:00 UTC unless the change is purely additive and non-locking.",
     "Production database schema migrations are blocked between 08:00 and 20:00 UTC unless the change is purely additive and non-locking.", None),
    ("Q13", "dev", 24, "operations", "filter", "Within the operations section, what is the retention period for system audit records?",
     "For operational telemetry and runtime debugging, system audit records are retained in hot storage for 180 days.",
     "For operational telemetry and runtime debugging, system audit records are retained in hot storage for 180 days.", {"section": "operations"}),
    ("Q14", "dev", 29, "compliance", "direct", "How quickly must a confirmed personal data breach be reported to the regulator?",
     "Any confirmed personal data breach must be reported to the external supervisory authority within 72 hours of discovery.",
     "Any confirmed personal data breach must be reported to the external supervisory authority within 72 hours of discovery.", None),
    ("Q15", "dev", 30, "compliance", "paraphrase", "How long does the system take to purge user records after an account deletion request?",
     "Upon receiving a verified right-to-erasure request, all personally identifiable user records are permanently purged within 14 days.",
     "Upon receiving a verified right-to-erasure request, all personally identifiable user records are permanently purged within 14 days.", None),

    # TEST (5 câu: Q16 -> Q20, có 2 câu filter)
    ("Q16", "test", 5, "security", "direct", "How many consecutive failed login attempts lock a developer account?",
     "A developer account is locked for 30 minutes after 6 consecutive failed multi-factor authentication attempts.",
     "A developer account is locked for 30 minutes after 6 consecutive failed multi-factor authentication attempts.", None),
    ("Q17", "test", 11, "architecture", "paraphrase", "What is the target recovery point objective (RPO) for tier-1 transactional databases?",
     "Tier-1 transactional databases maintain continuous WAL shipping to guarantee a Recovery Point Objective (RPO) of under 30 seconds.",
     "Tier-1 transactional databases maintain continuous WAL shipping to guarantee a Recovery Point Objective (RPO) of under 30 seconds.", None),
    ("Q18", "test", 18, "deployment", "conditional", "Under what exception can a hotfix bypass the staging soak period?",
     "Every release must complete a 24-hour staging soak period, except for zero-day security hotfixes approved by the VP of Engineering.",
     "Every release must complete a 24-hour staging soak period, except for zero-day security hotfixes approved by the VP of Engineering.", None),
    ("Q19", "test", 31, "compliance", "filter", "According to the compliance section, what is the mandatory retention period for system audit records?",
     "To satisfy financial and statutory regulations, system audit records are archived in immutable cold storage for 7 years.",
     "To satisfy financial and statutory regulations, system audit records are archived in immutable cold storage for 7 years.", {"section": "compliance"}),
    ("Q20", "test", 25, "operations", "filter", "In the operations section, what is the default timeout threshold for background health jobs?",
     "In routine cluster operations, the default request timeout threshold for background maintenance jobs is 300 seconds.",
     "In routine cluster operations, the default request timeout threshold for background maintenance jobs is 300 seconds.", {"section": "operations"}),
]


def build_all() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = data_dir / "cloud_handbook_v2.pdf"

    fact_by_useful_page = {f[2]: f for f in FACTS}

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    # Physical Page 1: Cover Page
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 120, "Cover Page - Open Cloud Engineering Handbook v2.0")
    c.showPage()

    # Physical Page 2: Table of Contents
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 100, "Table of Contents")
    c.showPage()

    useful_page_ids = []
    total_chars = 0

    for useful_idx in range(1, 36):
        phys_page = useful_idx + 2
        section = SECTIONS[(useful_idx - 1) // 7]
        header = f"Section: {section} | Cloud Engineering Handbook v2.0 | Useful Unit #{useful_idx:02d} (Physical Page {phys_page})"

        para1 = (
            f"[{section.upper()}] Module {useful_idx:02d} establishes standardized operational and architectural procedures "
            f"for distributed microservices running inside our production Kubernetes clusters. Engineers must adhere to "
            f"the resource quotas, observability tags, and network policies defined in this chapter to ensure high availability."
        )

        if useful_idx in fact_by_useful_page:
            f_item = fact_by_useful_page[useful_idx]
            para2 = (
                f"Policy Specification ({f_item[0]}): {f_item[7]} "
                f"Furthermore, teams must verify this configuration during quarterly readiness reviews and automated CI checks."
            )
        else:
            para2 = (
                f"Standard Guideline {useful_idx:02d}: Services deployed within the {section} domain must export Prometheus "
                f"metrics on port 9090 every 15 seconds and maintain structured JSON logs with trace_id correlation."
            )

        para3 = (
            f"Implementation Notes for Unit {useful_idx:02d}: When integrating legacy workloads into the {section} boundary, "
            f"platform maintainers should validate TLS 1.3 mutual authentication, enforce strict circuit-breaker budgets, "
            f"and document any regional failover dependencies in the service catalog."
        )

        full_page_text = f"{header}\n\n{para1}\n\n{para2}\n\n{para3}"
        total_chars += len(full_page_text)
        useful_page_ids.append(phys_page)

        text_obj = c.beginText(50, height - 60)
        text_obj.setFont("Helvetica", 10)
        for paragraph in [header, "", para1, "", para2, "", para3]:
            words = paragraph.split(" ")
            line = ""
            for w in words:
                if len(line) + 1 + len(w) <= 85:
                    line = (line + " " + w).strip()
                else:
                    text_obj.textLine(line)
                    line = w
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.showPage()

    c.save()

    manifest = {
        "corpus_name": "Open Cloud Engineering Handbook",
        "counting_rule": "Physical pages = 37. Excluded physical page 1 (Cover Page) and page 2 (Table of Contents). Useful content pages = 35 (pages 3..37).",
        "documents": [
            {
                "source_id": "cloud_handbook_v2",
                "title": "Open Cloud Engineering & Security Handbook",
                "source_path_or_url": "data/cloud_handbook_v2.pdf",
                "local_path": "data/cloud_handbook_v2.pdf",
                "license_or_permission": "CC-BY-4.0 (Synthetic Public Technical Handbook for Day 06 Lab)",
                "accessed_at": datetime.date.today().isoformat(),
                "version": "2.0",
                "physical_pages": 37,
                "counted_useful_pages": 35,
                "counted_page_numbers": useful_page_ids,
                "excluded_pages": [1, 2],
                "total_normalized_chars": total_chars,
            }
        ],
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    questions_list = []
    for q_id, split, u_idx, sec, q_type, q_text, ans, ev, flt in FACTS:
        questions_list.append(
            {
                "id": q_id,
                "split": split,
                "question_type": q_type,
                "question": q_text,
                "expected_answer": ans,
                "gold_source_id": "cloud_handbook_v2",
                "gold_page": u_idx + 2,
                "evidence_quote": ev,
                "filter": flt,
            }
        )

    benchmark = {
        "benchmark_version": "1.0",
        "split_policy": "Fixed before experimentation: 15 dev questions (Q01-Q15) and 5 test questions (Q16-Q20). Includes 5 metadata filter questions (3 dev, 2 test).",
        "questions": questions_list,
    }
    (data_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {pdf_path} (37 physical pages, 35 useful pages) + manifest.json + benchmark.json (20 questions).")


if __name__ == "__main__":
    build_all()
