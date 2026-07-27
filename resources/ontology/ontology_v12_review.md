# Ghi nhận quyết định ontology v12

V12 được sinh từ v11 bằng `migrate_ontology_v12`. V11 được giữ nguyên để các
báo cáo Stage A–B còn tái lập được.

| Vấn đề | Quyết định trong v12 |
|---|---|
| Điều kiện xét tốt nghiệp | Đồng bộ `condition` với `content`; gộp ràng buộc hình sự và kỷ luật thành một điều kiện; bổ sung GDQP-AN và GDTC. |
| Điều kiện xét học bổng | Bổ sung điều kiện không bị kỷ luật từ mức khiển trách trở lên. |
| Kết quả xét học bổng | Đủ điều kiện chỉ được đưa vào danh sách xét; việc cấp học bổng còn phụ thuộc xếp hạng và chỉ tiêu. |
| Vai trò trong chuyển ngành | `receivedBy` trỏ Phòng Công tác Chính trị và Sinh viên; `handledBy` tiếp tục trỏ Phòng Đào tạo Đại học. |

## Ý nghĩa của hai quan hệ phòng ban

```text
MajorChangeProcedure
├── receivedBy → StudentAffairsOffice
└── handledBy  → UndergraduateEducationOffice
```

- Câu hỏi về nơi nộp hoặc nơi nhận hồ sơ đi qua `receivedBy`.
- Câu hỏi về đơn vị xử lý hồ sơ đi qua `handledBy`.
- Không gán cả hai phòng vào `handledBy`, vì khi đó kết quả mất vai trò và
  backend buộc phải suy đoán.

## Kiểm tra kỹ thuật

- 57 thực thể có IRI đều có `rdfs:label@vi`.
- Không có canonical label trùng nhau.
- Mọi object/datatype property đều có domain và range.
- Không có IRI nội bộ được tham chiếu nhưng chưa khai báo.
- Ontology parse được bằng RDFLib và mở rộng OWL-RL thành công.
- 1.112 target SPARQL của dataset v1 vẫn thực thi và không có kết quả rỗng.
