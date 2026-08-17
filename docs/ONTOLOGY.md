# Ontology và nguồn dữ liệu

Tệp này trả lời dữ kiện học vụ trong dự án đến từ đâu và được tổ chức ra sao. Tệp dành cho người cần kiểm tra mức độ truy xuất được nguồn mà không đọc mã nguồn.

## Ontology là gì

Ontology là tập dữ kiện cùng các liên kết giữa chúng, được tổ chức để máy có thể tra cứu. Trong dự án, ontology liên kết quy định, thủ tục, biểu mẫu, bảng và phần văn bản làm căn cứ.

Một node là một mục dữ liệu trong ontology. Node có thể là một điều của quy chế, một thủ tục, một biểu mẫu hoặc một bảng. Các liên kết cho biết mục nào thuộc văn bản nào và dữ kiện nào dựa trên phần nguồn nào.

## Nguồn dữ liệu

Ontology được xây từ các văn bản chính thức của Trường Đại học Nha Trang:

- Quyết định 1052 về quy chế đào tạo đại học và các phụ lục.
- Quyết định 626 về quy chế tuyển sinh.
- Quyết định 1965 sửa đổi phụ lục.
- Phần còn hiệu lực của Quyết định 753.
- Quyết định 317 về học bổng.
- Phụ lục II của Quyết định 729 về ngành đào tạo.
- Hướng dẫn thanh toán và danh mục biểu mẫu.

Mỗi mục được lưu cùng thông tin nguồn để người dùng có thể đối chiếu lại văn bản gốc.

Ontology là cơ sở dữ liệu nội dung duy nhất của hệ thống. Không có kho văn bản
thứ hai, không có bảng dữ liệu song song: mọi dữ kiện mà công cụ trả về đều đọc
ra từ đây. Một nguồn duy nhất là cách để hai chỗ không nói hai điều khác nhau về
cùng một quy định.

## Danh mục khả năng trả lời

Từ ontology, dự án sinh ra một danh mục khả năng trả lời, lưu ở
`answer_inventory.json`. Mỗi mục trong danh mục là một đường đi hợp lệ từ một
node tới một dữ kiện đọc được.

Danh mục hiện ghi nhận 4.064 khả năng trả lời được hỗ trợ. Đây là số đường đi
hợp lệ trong đồ thị, không phải số câu hỏi hệ thống đã trả lời đúng.

Danh mục này trả lời câu hỏi "hệ thống có thể trả lời được những gì", và nó được
sinh lại từ ontology chứ không viết tay, nên nó không thể hứa nhiều hơn thứ đồ
thị thật sự có.

## Cách tổ chức nội dung

| Nhóm mục | Nội dung |
|---|---|
| Mục văn bản | Chương, điều, khoản, điểm, phụ lục và bảng của tài liệu. |
| Mục nghiệp vụ | Thủ tục, điều kiện, bước thực hiện, biểu mẫu, ngành và chứng chỉ. |
| Nguồn | Trích dẫn và đường dẫn tới văn bản gốc. |

SPARQL là ngôn ngữ dùng để hỏi ontology. Người dùng không cần viết SPARQL; hệ thống chỉ chạy các câu truy vấn nằm trong 50 khuôn đã định.

## Bảng và trích dẫn

Bảng được giữ nguyên khối, gồm tiêu đề, hàng, cột và ô trống. Cách lưu này tránh làm thay đổi nghĩa của bảng khi tách thành các mẩu dữ liệu nhỏ.

Kết quả tra cứu cần gồm:

- dữ kiện đọc được;
- trích dẫn cho biết dữ kiện thuộc phần nào của tài liệu;
- đường dẫn tới văn bản gốc.

## Giới hạn của dữ liệu

- Không lưu mức học phí riêng của từng người vì thông tin này phụ thuộc đăng ký thực tế.
- Không tự điền phần bị thiếu hoặc mơ hồ trong văn bản nguồn.
- Không tự giải quyết mọi thay đổi hiệu lực theo thời gian giữa các văn bản.

## Kiểm tra

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/ontology -q
```

Lệnh đầu kiểm tra sự liên kết giữa ontology, danh mục khuôn truy vấn và bộ câu hỏi. Lệnh sau kiểm tra riêng nội dung và nguồn của ontology.

## Tài liệu liên quan

- [Khái niệm và phạm vi](CONCEPT.md)
- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Bộ câu hỏi](DATASET.md)
