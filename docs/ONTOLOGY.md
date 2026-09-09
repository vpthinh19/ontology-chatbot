# Ontology và nguồn dữ liệu

Tài liệu này mô tả ontology như một sản phẩm dữ liệu: nó lưu gì, được tạo theo
cách nào, có thể truy nguồn tới đâu và các phép kiểm hiện tại chưa bảo đảm điều
gì. Văn bản chính thức của Trường Đại học Nha Trang là thẩm quyền chuẩn tắc;
ontology chỉ là **cơ sở dữ liệu nội dung duy nhất của runtime**.

## 1. Phạm vi và mô hình khái niệm

Ontology dùng namespace `http://www.ntu.edu.vn/ontology/academic#` và được lưu
bằng Turtle tại [`resources/ontology/ontology.ttl`](../resources/ontology/ontology.ttl).
Đồ thị chia thành hai tầng đều có thể được truy vấn trực tiếp:

| Tầng | Đơn vị chính | Mục đích |
|---|---|---|
| Văn bản | quyết định, quy chế, chương, điều, khoản, điểm, phụ lục, mục, bảng | giữ nội dung và vị trí trích dẫn |
| Nghiệp vụ | thủ tục, bước, điều kiện, thời hạn, trường hợp, quy tắc, biểu mẫu, ngành, chứng chỉ | biểu diễn dữ kiện theo khái niệm để truy xuất |

Hai tầng nối bằng `basedOn`. Một node nghiệp vụ cần dẫn tới phần văn bản nhỏ
nhất được dùng làm căn cứ. Quyết định ban hành và quy chế kèm theo là hai tài
liệu riêng: chúng có thể cùng có “Điều 1” nhưng nội dung và vai trò khác nhau.

Các quyết định mô hình hoá đáng chú ý:

- bước, điều kiện, thời hạn và kết quả là node riêng thay vì một đoạn mô tả
  phẳng;
- điều kiện chỉ áp dụng cho một trường hợp phải khai `scopedToCase`;
- một trường hợp dẫn tới nhiều thủ tục phải có điều kiện phân nhánh;
- quy tắc có ngưỡng vừa giữ câu nguyên văn vừa giữ trường số để so sánh;
- bảng trả nguyên khối Markdown, giữ ô trống, thay vì dựng lại từ danh sách cell;
- biểu mẫu trong quyết định và mục tải trên website là hai thực thể, nối bằng
  `catalogueEntryForForm`, vì số thứ tự của hai nguồn có thể khác nhau.

## 2. Giải phẫu snapshot

Các số dưới đây được sinh từ đồ thị hiện hành:

| Thành phần | Số lượng |
|---|---:|
| Bộ ba trong tệp Turtle | 6.350 |
| Bộ ba sau khi nạp và materialize nguồn | 7.704 |
| Lớp | 56 |
| Cá thể có tên | 685 |
| Object property | 29 |
| Datatype property | 55 |
| Đoạn `officialText` | 320 |
| Bảng `verbatimTableText` | 16 |
| Quan hệ `basedOn` khai báo | 368 |
| Node nhận trích dẫn và URL dẫn xuất | 677 |

Runtime bổ sung `sourceCitation` và `sourceLink` bằng cách đi theo `basedOn`.
677 node nhận hai thuộc tính này, tạo 1.354 bộ ba dẫn xuất. Chúng là bản chiếu
để rút gọn truy vấn, không phải dữ kiện mới và không được ghi tay vào Turtle.

## 3. Nguồn

Đồ thị khai báo 17 tài nguyên chính thức:

- sáu quyết định: 1052, 1965, 317, 626, 729 và 753;
- ba quy chế đi kèm các quyết định 1052, 626 và 753;
- tám nguồn web/hướng dẫn: tuyển sinh, cơ cấu tổ chức, thông báo và tiêu chuẩn
  học bổng, tra cứu và hướng dẫn đóng học phí, VNPAY, danh mục biểu mẫu.

Nguồn văn bản có thể có số hiệu/ngày ban hành; nguồn web dùng `retrievedDate` để
ghi ngày snapshot. Bản sao PDF/Markdown trong [`references/`](../references/)
phục vụ đối chiếu, nhưng không phải cả 17 tài nguyên đều có bản sao cục bộ cùng
định dạng.

Ontology xử lý hiệu lực theo từng trường hợp đã biên soạn, không có reasoner
pháp lý tổng quát. Ví dụ, nó giữ Điều 10 của quy chế 753 ở nơi quy chế 1052 được
người biên soạn xác định là không có nội dung thay thế tương ứng. Quyết định này
được test khoá lại, nhưng vẫn là một phán đoán biên tập cần chuyên gia nghiệp vụ
rà khi văn bản thay đổi.

## 4. Quy trình tạo và bảo trì

1. Chọn nguồn chính thức trong phạm vi nghiên cứu; ghi định danh và URL.
2. Chuyển phần cần dùng thành text/Markdown và tách cấu trúc văn bản.
3. Khai lược đồ cho khái niệm, quan hệ và kiểu literal.
4. Biên soạn thủ công node nghiệp vụ từ nội dung nguồn.
5. Nối mỗi node mang câu trả lời tới căn cứ bằng `basedOn`.
6. Nạp đồ thị để materialize trích dẫn/URL.
7. Sinh `answer_inventory.json`, catalogue coverage, báo cáo và checksum.
8. Chạy kiểm định trước khi công bố hoặc huấn luyện lại.

Không có pipeline tự động nhận nguồn thô và tái tạo hoàn chỉnh ontology. Tầng
nghiệp vụ được viết tay. Vì vậy quy trình hiện tái kiểm được snapshot và nhiều
bất biến, nhưng chưa tái lập đầu-cuối quá trình trích xuất.

Khi cập nhật một nguồn cần tối thiểu:

- lưu hoặc định danh snapshot nguồn mới;
- xác định văn bản mới bổ sung, sửa đổi hay thay thế phạm vi nào;
- sửa tầng văn bản trước, sau đó sửa các node nghiệp vụ dẫn tới nó;
- kiểm lại mọi `basedOn`, ngưỡng số, bảng và tên thay thế bị ảnh hưởng;
- sinh lại inventory/report/manifest;
- huấn luyện lại bộ phân loại nếu không gian nhãn hoặc dữ liệu học thay đổi;
- không tái sử dụng metric cũ khi fingerprint đầu vào đã đổi.

## 5. Danh mục khả năng trả lời

[`answer_inventory.json`](../resources/ontology/answer_inventory.json) được dẫn
xuất từ ontology. Mỗi mục là một đường đi từ một neo đến literal trả lời được và
kèm node căn cứ.

| Trạng thái | Số lượng | Ý nghĩa |
|---|---:|---|
| `supported` | 4.057 | catalogue có ít nhất một họ truy vấn bao phủ |
| `excluded` | 23 | cố ý không cho truy xuất theo đường đó, có lý do |
| Tổng | 4.080 | đường có dữ liệu, không phải số câu hỏi tự nhiên |

23 mục loại gồm 16 bản `officialText` phẳng của bảng, 6 nhãn bản ghi ngưỡng nội
bộ và 1 quan hệ biểu mẫu không có căn cứ trong Điều 29. Catalogue bao phủ đủ
4.057 mục hỗ trợ; một mục nhãn `University-rdfs-label` được hai họ bao phủ có
chủ đích.

## 6. Tính chất được kiểm tự động

Nhóm `tests/ontology` và validator canh các bất biến sau:

- lược đồ được khai đầy đủ, đúng quy ước tên và có nhãn tiếng Việt;
- mọi cá thể có tên có nhãn; tên chính/tên phụ không trỏ tới hai thực thể;
- node nghiệp vụ chính có căn cứ; bước và điều kiện không bị rơi khỏi thủ tục;
- phần văn bản lá của các nguồn có bản text cục bộ khớp nguồn sau khi chỉ chuẩn
  hoá hình thức;
- 16 bảng khớp từng ký tự với bảng Markdown nguồn;
- văn bản cấp con nằm trong văn bản cấp cha;
- dữ kiện số đủ dài xuất hiện trong đoạn hoặc URL được nó viện dẫn;
- mọi đích dataset tạo được truy vấn và trả ít nhất một dòng.

Chạy:

```bash
uv run validate_sparql_dataset
uv run pytest tests/ontology -q
```

Các phép kiểm không đánh giá độ đầy đủ của tập nguồn, không thay thế rà soát pháp
lý, không chứng minh nguồn web còn mới và không chấm chất lượng diễn đạt của LLM.

## 7. Giới hạn dữ liệu

- Không lưu hồ sơ, điểm hay số tiền phải đóng của một sinh viên cụ thể.
- Không tự điền dữ kiện mơ hồ hoặc thiếu trong nguồn.
- Không suy luận phủ định chỉ từ việc thiếu một triple.
- Không giải quyết tổng quát hiệu lực theo thời gian và xung đột văn bản.
- Không có double annotation độc lập cho tầng nghiệp vụ.
- Không có tỷ lệ bao phủ so với toàn bộ nghiệp vụ thực tế của trường.
- Việc một đường được catalogue bao phủ chỉ chứng minh khả năng truy xuất kỹ
  thuật, không chứng minh người dùng sẽ gọi đúng đường đó.

## 8. Chuỗi thẩm quyền

Khi hai nơi mâu thuẫn, sử dụng thứ tự sau:

1. văn bản/trang chính thức tại thời điểm áp dụng;
2. snapshot nguồn cục bộ để điều tra lịch sử;
3. `ontology.ttl` dùng cho runtime;
4. `catalogue.jsonl` mô tả đường truy xuất;
5. dataset mô tả câu hỏi và đích học;
6. inventory, manifest và report là artifact dẫn xuất;
7. câu trả lời của model không phải nguồn.

## Tài liệu liên quan

- [README nghiên cứu](../README.md)
- [Bộ dữ liệu](DATASET.md)
- [Câu hỏi phản biện](DEFENSE.md)
