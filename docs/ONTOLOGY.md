# Ontology và nguồn dữ liệu

Tệp này trả lời dữ kiện học vụ đến từ đâu và được tổ chức ra sao.

## Khái niệm

Ontology là tập dữ kiện cùng các liên kết giữa chúng để máy tra cứu. Một node là một mục dữ liệu, như điều của quy chế, thủ tục, biểu mẫu hoặc bảng.

Ontology là cơ sở dữ liệu nội dung duy nhất của hệ thống. Mọi dữ kiện công cụ trả về đều được đọc từ đây.

## Nguồn dữ liệu

Ontology được xây từ văn bản chính thức của Trường Đại học Nha Trang:

- Quyết định 1052 về quy chế đào tạo đại học và phụ lục.
- Quyết định 626 về quy chế tuyển sinh.
- Quyết định 1965 sửa đổi phụ lục.
- Phần còn hiệu lực của Quyết định 753.
- Quyết định 317 về học bổng.
- Phụ lục II của Quyết định 729 về ngành đào tạo.
- Hướng dẫn thanh toán và danh mục biểu mẫu.

Mỗi mục giữ thông tin nguồn để người dùng đối chiếu văn bản gốc.

## Danh mục khả năng trả lời

Từ ontology, dự án sinh danh mục khả năng trả lời ở `answer_inventory.json`. Mỗi mục là một đường đi hợp lệ từ một node tới một dữ kiện đọc được.

Danh mục hiện ghi nhận 4.064 khả năng trả lời được hỗ trợ. Đây là số đường đi hợp lệ trong đồ thị, không phải số câu hỏi trả lời đúng.

## Cách lưu và trả kết quả

| Nhóm mục | Nội dung |
|---|---|
| Mục văn bản | Chương, điều, khoản, điểm, phụ lục và bảng. |
| Mục nghiệp vụ | Thủ tục, điều kiện, bước thực hiện, biểu mẫu, ngành và chứng chỉ. |
| Nguồn | Trích dẫn và đường dẫn tới văn bản gốc. |

Bảng được giữ nguyên tiêu đề, hàng, cột và ô trống. Kết quả tra cứu gồm dữ kiện, trích dẫn và đường dẫn nguồn.

## Giới hạn dữ liệu

- Không lưu mức học phí riêng của từng người.
- Không tự điền phần thiếu hoặc mơ hồ trong nguồn.
- Không tự giải quyết mọi thay đổi hiệu lực theo thời gian giữa các văn bản.

## Kiểm tra

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/ontology -q
```

Lệnh đầu kiểm tra sự liên kết giữa ontology, danh mục khuôn truy vấn và bộ câu hỏi. Lệnh sau kiểm tra nội dung và nguồn của ontology.

## Tài liệu liên quan

- [Khái niệm và phạm vi](CONCEPT.md)
- [Bộ câu hỏi](DATASET.md)
