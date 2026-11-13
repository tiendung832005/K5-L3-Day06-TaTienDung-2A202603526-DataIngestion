# Báo cáo cá nhân — Day 6

- **Học viên:** Tạ Tiến Dũng
- **MSSV:** 2A202603526
- **Lớp:** K5-L3A

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - **Chủ đề:** Tài liệu hướng dẫn kỹ thuật & vận hành hệ thống Cloud (_Open Cloud Engineering & Security Handbook v2.0_), lưu tại `starter/data/cloud_handbook_v2.pdf`, manifest quản lý tại `starter/data/manifest.json`.
  - **Quyền sử dụng:** Giấy phép mở `CC-BY-4.0` (tài liệu kỹ thuật tổng hợp phục vụ thực hành Day 06, không chứa dữ liệu cá nhân hay thông tin mật).
  - **Số trang và quy tắc tính trang:** Tài liệu có tổng cộng **37 trang vật lý**. Áp dụng quy tắc lọc tự động loại bỏ trang bìa (trang 1, 49 ký tự), trang mục lục (trang 2, 17 ký tự) và các trang có dưới 100 ký tự nội dung. Số trang nội dung hữu ích đưa vào pipeline là **35 trang** (từ trang vật lý `3` đến `37`), tổng cộng `31.745` ký tự sau chuẩn hóa.
- **Chuẩn hóa, lỗi và giới hạn:**
  - **Chuẩn hóa:** Văn bản trích xuất qua `pypdf` được chuẩn hóa về dạng Unicode `NFC`, loại bỏ ký tự điều khiển ẩn, tách ranh giới đoạn văn theo `\n\n` và nối các dòng bị ngắt cứng bên trong cùng một đoạn thành câu liền mạch.
  - **Lỗi đã phát hiện và xử lý:** Ở lần kiểm tra đầu tiên, `pypdf` giữ lại ký tự xuống dòng mềm ở cuối mỗi dòng in PDF khiến 20/20 câu `evidence_quote` bị lệch khớp chuỗi (`Evidence mismatches: 20`). Sau khi cập nhật `normalize_text()` để nối dòng trong cùng đoạn văn mà vẫn giữ `\n\n` phân cách đoạn, tỷ lệ khớp đạt `0` lỗi. Ngoài ra, xử lý trường hợp biến môi trường `EMBEDDING_MODEL` để trống trong `.env` bằng fallback mặc định rõ ràng (không fallback sang vector giả).
  - **Giới hạn:** Tài liệu dạng text PDF sạch, chưa kiểm thử quy trình OCR cho tài liệu scan hoặc bảng biểu phức tạp nhiều cột.
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - **Embedding model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (chạy local qua thư viện `sentence-transformers`), số chiều: **384**, chuẩn hóa L2 (`normalize_embeddings=True`).
  - **Vector store:** `ChromaDB` chế độ lưu bền vững local (`chromadb.PersistentClient` lưu tại `starter/chroma_db`), sử dụng chỉ mục HNSW tìm kiếm xấp xỉ (ANN) với độ đo **Cosine similarity** (`"hnsw:space": "cosine"`). Có kiểm tra tính bất biến khi nạp lại (re-ingest idempotency): nạp lại cùng phiên bản giữ nguyên số lượng chunk (`72` cho A, `70` cho B/C) và tự động xóa chunk lỗi thời nếu tài liệu thay đổi.
  - **Lệnh chạy tái lập:**
    ```powershell
    cd starter
    .\.venv\Scripts\Activate.ps1
    python scripts/generate_corpus_and_benchmark.py
    python -m src.run
    python scripts/run_manual_audit.py
    ```
  - **Chi phí:** **$0.00** (chạy hoàn toàn local trên CPU).
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - **Metadata bắt buộc:** `document_id` (`string`), `source` (`string`), `page` (`int` — số trang vật lý trong PDF), `chunk_id` (`string`).
  - **Trường lọc bổ sung:** `section` (`string`), nhận 5 giá trị phân biệt được trích xuất trực tiếp từ tiêu đề từng chương trong nguồn: `security`, `architecture`, `deployment`, `operations`, `compliance` (kèm `version`: `"2.0"`).
  - **Lý do chọn:** Trong tài liệu kỹ thuật, nhiều chương cùng đề cập tới các khái niệm chung như _timeout threshold_ hay _audit retention period_ nhưng với quy định và thông số khác nhau. Trường `section` giúp khoanh vùng phạm vi truy xuất theo đúng ngữ cảnh chương mà người dùng hỏi.

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **Chiến lược A (`fixed_size`):** Cắt văn bản theo cửa sổ cố định `size = 500` ký tự, `overlap = 50` ký tự; lưu metadata truy nguồn; truy xuất Top-3 không áp dụng filter (`use_filter = False`).
  - **Chiến lược B (`by_paragraph`):** Gom nhóm theo ranh giới đoạn văn (`\n\n`) với giới hạn `max_size = 600` ký tự (tự chia theo câu nếu đoạn vượt ngưỡng); lưu cùng metadata như A; truy xuất Top-3 không áp dụng filter (`use_filter = False`).
  - **Chiến lược C (`by_paragraph + filter`):** Giữ nguyên toàn bộ cấu hình chia chunk, embedding và index của B; **khác biệt duy nhất giữa B và C** là bật bộ lọc metadata (`where={"section": ...}`) khi câu hỏi cung cấp sẵn điều kiện lọc chương (`use_filter = True`), và chạy không filter cho các câu hỏi còn lại.
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:**
  - Bộ benchmark (`starter/data/benchmark.json`) gồm **20 câu hỏi** được khóa cứng trước khi chạy thử nghiệm: **15 câu `dev`** (`Q01`–`Q15`) và **5 câu `test`** (`Q16`–`Q20`).
  - Bao phủ đa dạng dạng câu hỏi: trực tiếp (_direct_), diễn đạt lại (_paraphrase_), điều kiện/ngoại lệ (_conditional_), và **5 câu kiểm tra metadata filter** (`Q04`, `Q08`, `Q13` ở `dev`; `Q19`, `Q20` ở `test` — giá trị filter là input ngữ cảnh người dùng cung cấp trước khi truy xuất, không chứa `gold_page` hay đáp án).
  - **Cách kiểm chứng evidence:** Toàn bộ 20 câu đều được chạy kiểm tra tự động trước khi đánh giá để xác nhận `evidence_quote` tồn tại nguyên vẹn trên đúng trang `gold_page` của văn bản đã chuẩn hóa (`Evidence mismatches: 0`).
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:**
  - Ưu tiên theo thứ tự: (1) **Evidence Hit@3** và **Grounding Quality** cao nhất để đảm bảo không bỏ sót bằng chứng kèm điều kiện ngoại lệ; (2) **Tỷ lệ tuân thủ filter** đạt 100% khi có yêu cầu lọc; (3) **Chunk Coherence** cao và chi phí/thời gian nạp dữ liệu thấp.

## Kết quả

| Strategy | Split | Hit@1 (n/N)  | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
| -------- | ----- | ------------ | -------------------- | ----------- | --------- | ------- |
| A        | dev   | 1/15 (6.7%)  | 2/15 (13.3%)         | 72          | 3.215s    | $0.00   |
| A        | test  | 0/5 (0.0%)   | 0/5 (0.0%)           | 72          | 3.215s    | $0.00   |
| B        | dev   | 9/15 (60.0%) | 9/15 (60.0%)         | 70          | 2.760s    | $0.00   |
| B        | test  | 3/5 (60.0%)  | 3/5 (60.0%)          | 70          | 2.760s    | $0.00   |
| C        | dev   | 9/15 (60.0%) | 9/15 (60.0%)         | 70          | 2.855s    | $0.00   |
| C        | test  | 3/5 (60.0%)  | 3/5 (60.0%)          | 70          | 2.855s    | $0.00   |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A)          | Grounding 0/1/2 (số câu) và trung bình /2 |
| -------- | --------------------------- | ------------------------- | --------------------------------------- | ----------------------------------------- |
| A        | 1.00/2 (n=10)               | 15/15 (100.0%)            | dev: 0/3 (0.0%) \| test: 0/2 (0.0%)     | 0: 0 / 1: 5 / 2: 0 — TB: **1.00/2**       |
| B        | 2.00/2 (n=10)               | 15/15 (100.0%)            | dev: 1/3 (33.3%) \| test: 1/2 (50.0%)   | 0: 1 / 1: 1 / 2: 3 — TB: **1.40/2**       |
| C        | 2.00/2 (n=10)               | 15/15 (100.0%)            | dev: 3/3 (100.0%) \| test: 2/2 (100.0%) | 0: 1 / 1: 1 / 2: 3 — TB: **1.40/2**       |

- **Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
  - Trace truy xuất Top-3 đầy đủ (60 lượt truy xuất): `starter/results/traces_top3.json`.
  - Bảng tổng hợp chỉ số tự động: `starter/results/metrics_summary.json`.
  - Log trang bị loại trừ: `starter/results/ingestion_errors.json`.
  - Nhãn chấm thủ công chi tiết: `starter/results/manual_audit_report.json` (tác giả tự chấm; lưu ý nguy cơ thiên lệch xác nhận do người chấm đồng thời là người xây dựng corpus và benchmark).
  - **Cách chọn mẫu:** Coherence chấm cố định trên 10 trang hữu ích đầu tiên đã sắp xếp (`cloud_handbook_v2_p003` đến `p012`) cho cả 3 chiến lược (30 mẫu); Metadata kiểm tra toàn bộ `5 câu test × top-3 = 15 bản ghi/chiến lược`; Grounding chấm toàn bộ 5 câu `test` (`Q16`–`Q20`).
  - **Nhận xét hữu dụng của metadata:** Trường `section` giúp lọc bỏ triệt để các chunk nhiễu từ chương khác khi có câu hỏi theo phạm vi chương (như `Q20` ở C loại bỏ hoàn toàn 2 trang nhiễu chương `security` mà B mắc phải). Hạn chế: filter cứng dạng exact-match yêu cầu câu hỏi người dùng phải xác định đúng tên `section` trước khi truy xuất; nếu người dùng gán sai hoặc không nêu rõ chương, filter có thể vô tình loại bỏ mất tài liệu đúng.

## Phân tích và kết luận

- **So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:**
  - **Tác động A $\rightarrow$ B (Chunking):** Chuyển từ cắt cố định 500 ký tự (A) sang gom theo đoạn văn tối đa 600 ký tự (B) giúp `Hit@1` trên `dev` tăng vọt từ `1/15 (6.7%)` lên `9/15 (60.0%)`, trên `test` tăng từ `0/5 (0.0%)` lên `3/5 (60.0%)`, `Coherence` tăng từ `1.00/2` lên `2.00/2`, đồng thời giảm số chunk từ `72` xuống `70` và rút ngắn thời gian ingest từ `3.215s` xuống `2.760s`. Nguyên nhân là A cắt "mù" theo số ký tự nên làm đứt ngang câu bằng chứng ở ranh giới 500 ký tự.
  - **Tác động B $\rightarrow$ C (Metadata Filter):** Giữ nguyên chunking của B nhưng bật filter `section` ở C giúp tỷ lệ tuân thủ phạm vi filter tăng từ `1/3 (33.3%)` lên `3/3 (100.0%)` trên `dev` và từ `1/2 (50.0%)` lên `2/2 (100.0%)` trên `test`, loại bỏ hoàn toàn các chunk nhiễu ngoài chương được hỏi.
  - **Ví dụ sai 1 (`Q16` trên Chiến lược A — nguồn `data/cloud_handbook_v2.pdf`, `gold_page = 7`):** Câu hỏi về số lần đăng nhập sai bị khóa tài khoản. A truy xuất được trang `7` ở hạng 3 (`[p.32, p.18, p.7]`), nhưng do cắt cứng ở ký tự 500 nên câu bằng chứng _"A developer account is locked for 30 minutes after 6 consecutive failed multi-factor authentication attempts."_ bị tách làm đôi sang chunk tiếp theo, khiến `Hit@3 = 0` và `Grounding = 1/2`. Khi chuyển sang B/C, câu này đạt `Hit@1 = 1` và `Grounding = 2/2`.
  - **Ví dụ sai 2 (`Q18` trên Chiến lược B & C — nguồn `data/cloud_handbook_v2.pdf`, `gold_page = 20`):** Câu hỏi về điều kiện ngoại lệ bỏ qua _24-hour staging soak period_ (`section: deployment`). Cả B và C đều trả về `[p.17, p.17, p.10]` (`Grounding = 0/2`), bốc nhầm sang trang `17` (cũng nằm trong `deployment`, nói về `canary deployment rollouts` và `release`) do từ vựng ngữ cảnh khá tương đồng, khiến filter theo `section` không thể phân biệt hai trang cùng chương.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - **Chọn Chiến lược C (`by_paragraph` + `metadata filter`):** Đạt hiệu suất cao nhất đồng đều trên mọi tiêu chí (`Hit@3 = 60%`, `Coherence = 2.00/2`, `Grounding = 1.40/2`, `Filter compliance = 100%`, chi phí `$0.00`).
  - **Đánh đổi & Điều kiện áp dụng:** C yêu cầu dữ liệu đầu vào phải có cấu trúc phân đoạn rõ ràng và bộ trích xuất metadata tin cậy. Khi dữ liệu là văn bản thô không có xuống dòng đoạn văn hoặc truy vấn người dùng không cung cấp ngữ cảnh filter, C sẽ tự động lùi về hành vi tương đương B.
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - Tập `test` chỉ gồm **5 câu hỏi** nên mỗi câu tương ứng tới 20% tỷ lệ phần trăm — chỉ mang tính minh họa cho corpus này, chưa đủ ý nghĩa thống kê để khái quát hóa cho mọi bộ tài liệu.
  - Corpus có nhiều đoạn mô tả khung lặp lại giữa các chương (`Standard Guideline`, `Implementation Notes`), tạo độ nhiễu cao cho embedding thuần ngữ nghĩa (`MiniLM-L12-v2`).
  - Nhãn chấm thủ công do tác giả tự thực hiện nên tồn tại rủi ro thiên lệch chủ quan.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?**
  - Kết hợp **Hybrid Retrieval (Dense Vector + BM25)** để bắt chính xác các thuật ngữ kỹ thuật đặc thù (như `"staging soak period"`, `"WAL shipping"`, `"X-Bypass-Cache"`) mà dense embedding dễ bị nhiễu bởi câu văn mẫu xung quanh.
  - Bổ sung bước **Cross-Encoder Reranking** trên Top-10 ứng viên để đẩy đúng chunk chứa thông số chi tiết lên vị trí Top-1.
