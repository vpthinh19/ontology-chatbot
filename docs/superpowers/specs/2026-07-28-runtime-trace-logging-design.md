# Runtime Trace Logging Design

## Mục tiêu

Mỗi lượt chat để lại trace terminal đủ để xác định lỗi nằm ở model, validator,
ontology hay renderer. Logging không thay đổi response HTTP hoặc output model.

## Hình dạng log

Mỗi request có `request_id` và các dòng INFO theo thứ tự:

1. câu gốc và câu sau `normalize_model_input`;
2. output model nguyên văn và thời gian sinh;
3. loại output: marker, SPARQL hợp lệ hoặc output lỗi;
4. số dòng ontology và thời gian validate/execute khi có query;
5. reply cùng tổng latency.

Ví dụ từ chối:

```text
INFO request=2a41 input='chào bạn nha' normalized='chào bạn nha'
INFO request=2a41 model output='không có thông tin' duration_ms=310.2
INFO request=2a41 reply='Không có thông tin.' total_ms=312.0
```

Ví dụ SPARQL:

```text
INFO request=761b model output='SELECT ?answer WHERE { :Procedure :content ?answer . }' duration_ms=382.1
INFO request=761b ontology rows=1 duration_ms=45.7
INFO request=761b reply='...' total_ms=431.8
```

Lỗi thật ghi ERROR với stage, request ID và stack trace. Không log token ID,
hidden state hoặc toàn bộ logits.

## Biên kiến trúc

`OntologyChatbot` điều phối và ghi trace cấp request. Generator, SPARQL executor
và renderer không log trùng cùng dữ liệu. CLI cấu hình standard-library
`logging`, nhận `--log-level` và không thêm telemetry/database log.

## Kiểm thử

- marker có input, output và reply nhưng không gọi RDFLib;
- SPARQL thành công có output, số dòng và reply;
- output/query lỗi ghi đúng stage;
- lỗi hệ thống có stack trace;
- test không phụ thuộc timestamp hoặc request ID cụ thể.
