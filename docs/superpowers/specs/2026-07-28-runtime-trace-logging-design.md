# Runtime Trace Logging Design

## Mục tiêu

Mỗi lượt chat phải để lại một trace dễ đọc trong terminal, đủ để xác định lỗi
nằm ở domain gate, model sinh SPARQL, validator/executor, ontology hay renderer.
Logging phục vụ chẩn đoán cục bộ; không thay đổi response HTTP hoặc kết quả mô
hình.

## Hình dạng log

Mỗi request có một `request_id` ngắn và các dòng `INFO` theo thứ tự:

1. `input`: câu gốc và câu sau `normalize_model_input`.
2. `gate`: xác suất `in_scope`, threshold, quyết định và thời gian.
3. `generator`: toàn bộ SPARQL model sinh ra và thời gian.
4. `ontology`: số dòng trả về và thời gian validate/execute.
5. `reply`: toàn bộ văn bản render và tổng thời gian.

Câu bị gate chặn kết thúc sau dòng `gate`. Lỗi thật ghi `ERROR` kèm stage,
request ID và stack trace rồi được re-raise để API giữ nguyên contract hiện
tại. Không log token ID, hidden state hoặc toàn bộ logits vì chúng không giúp
truy nguyên semantic và làm log khó đọc.

Ví dụ:

```text
INFO request=2a41 input='hc phí k65 cntt' normalized='học phí khoá 65 công nghệ thông tin'
INFO request=2a41 gate probability=0.560115 threshold=0.752740 accepted=false duration_ms=27.4
```

```text
INFO request=761b generator sparql='SELECT ?answer WHERE { :CourseRegistrationProcedure :condition ?answer . }' duration_ms=382.1
INFO request=761b ontology rows=0 duration_ms=45.7
INFO request=761b reply='Không tìm thấy thông tin phù hợp.' total_ms=456.8
```

## Biên kiến trúc

`OntologyChatbot` điều phối và ghi trace cấp request. `DomainGate` tiếp tục chỉ
trả `GateDecision`; protocol công bố thêm thuộc tính chỉ đọc `threshold` để
pipeline không đọc private state. Generator, SPARQL executor và renderer không
tự log cùng dữ liệu, tránh log trùng và tránh gắn logic quan sát vào các module
thuần.

CLI `serve_sparql` cấu hình standard-library `logging` và nhận
`--log-level`; mặc định là `INFO`. Không thêm dependency, file handler, JSON
logger, database log hoặc hệ thống telemetry.

## Kiểm thử

Kiểm thử dùng `caplog` để chứng minh:

- nhánh gate từ chối có input, probability, threshold và không có generator;
- nhánh thành công có SPARQL nguyên văn, số dòng và reply;
- nhánh lỗi có stage cùng stack trace;
- CLI mặc định bật `INFO` và chấp nhận đổi log level.

Các test không assert timestamp hoặc request ID cụ thể; chúng chỉ kiểm tra các
trường có ý nghĩa chẩn đoán.
