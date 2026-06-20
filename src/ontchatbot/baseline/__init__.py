"""Phase 8 — module BENCHMARK tách biệt: ontology vs CSDL phẳng (truy hồi).

⚠️ ĐỊNH VỊ: Phase 8 là phần BỔ SUNG cho trọn vẹn đề tài, KHÔNG phải lõi (lõi = model +
ontology). Mục tiêu: so end-to-end hệ ontology (duyệt cấu trúc, trả ĐÚNG TẬP) với một baseline
truy hồi MẠNH (BGE-M3 hybrid → BGE-reranker-v2-m3) để phơi ưu thế ở truy vấn CÓ CẤU TRÚC
(giao tập, đa-hop, chọn đúng FIELD). Báo cáo trung thực cả chỗ HOÀ (lookup đơn).

KIẾN TRÚC: module này **KHÔNG** nối vào ``serve.py``/``pipeline.py`` — chỉ "câu vào → kết quả ra".
Deploy chỉ chạy pipeline ontology. Eval dùng trọng số transformers thật (không phải CT2 deploy).
"""
