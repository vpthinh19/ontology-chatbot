# Ý tưởng hệ thống và ranh giới trả lời

## Vấn đề

Thông tin về một quy trình học vụ nằm rải rác: quy chế đào tạo, các phụ lục,
hướng dẫn thanh toán, danh mục biểu mẫu. Câu hỏi "bảo lưu nộp đơn ở đâu" không
chỉ cần tìm đoạn văn có chữ "bảo lưu", mà phải nối được thủ tục bảo lưu với đơn
vị tiếp nhận và tên chính thức của đơn vị đó.

Cách làm phổ biến là tìm đoạn văn gần nghĩa rồi trả về cả đoạn. Cách đó trả lời
được câu dễ, nhưng không phân biệt nổi bốn câu hỏi khác nhau về cùng một thủ tục
— cách làm, điều kiện, thời hạn, kết quả — vì cả bốn cùng rơi vào một đoạn văn.

## Cách tiếp cận

Dự án lưu kiến thức học vụ dưới dạng **mạng lưới có quan hệ rõ ràng** thay vì
văn bản trôi. Chatbot không tự nghĩ ra câu trả lời; nó **dịch câu hỏi tiếng Việt
thành một câu truy vấn** rồi để hệ thống chạy truy vấn đó trên mạng lưới và lấy
về dữ liệu.

Tách bạch này quan trọng: mô hình ngôn ngữ được phép học *tên gọi và quan hệ*
của mạng lưới, nhưng **không học thuộc nội dung câu trả lời**. Nội dung luôn nằm
trong mạng lưới và chỉ được lấy ra khi truy vấn thực sự chạy. Nhờ vậy sửa một
quy định trong mạng lưới là chatbot đổi câu trả lời ngay, không cần huấn luyện
lại.

## Mô hình sinh ra đúng một trong hai thứ

Với mỗi câu hỏi, mô hình sinh **một** kết quả:

- một câu truy vấn, nếu mạng lưới trả lời được câu hỏi;
- hoặc dòng chữ báo không có thông tin, nếu không.

Ví dụ:

```text
Hỏi:      phòng nào nhận hồ sơ bảo lưu
Mô hình:  (một truy vấn đi từ thủ tục nghỉ học tạm thời, theo quan hệ
           "nộp tại", lấy tên đơn vị)
Trả lời:  Phòng Công tác Chính trị và Sinh viên

Hỏi:      ngày mai Nha Trang có mưa không
Mô hình:  không có thông tin
Trả lời:  Không có thông tin.
```

Mô hình là nơi **duy nhất** quyết định câu hỏi có thuộc phạm vi hay không. Hệ
thống phía sau không có bộ phân loại thứ hai, không có ngưỡng tin cậy, không dò
đoán thực thể, và không tự sửa truy vấn sai.

## Ranh giới phạm vi

Một câu thuộc phạm vi khi mạng lưới trả lời được **toàn bộ** yêu cầu của nó.

Hệ thống từ chối trả lời khi: câu hỏi ngoài học vụ, dữ liệu không có trong mạng
lưới, câu quá mơ hồ để có một câu trả lời đúng duy nhất, trò chuyện xã giao, văn
bản vô nghĩa, và câu hỏi ghép nhiều ý mà có bất kỳ ý nào không được hỗ trợ. Với
câu ghép, hệ thống không trả lời một phần.

## Bốn lớp chặn, cùng một câu trả lời

Sau khi mô hình sinh ra truy vấn, hệ thống lần lượt kiểm tra:

1. truy vấn có đúng cú pháp và chỉ đọc dữ liệu, không sửa đổi gì;
2. truy vấn có thuộc một trong các dạng câu hỏi đã được khai báo trước;
3. truy vấn chạy được trên mạng lưới;
4. truy vấn thực sự trả về dữ liệu.

Trượt bất kỳ bước nào thì người dùng nhận đúng một câu: *Không có thông tin.*
Hệ thống thà im lặng còn hơn đoán.

Bước 2 đáng nói riêng. Một truy vấn có thể đúng cú pháp hoàn toàn mà vẫn ghép
một thực thể với một quan hệ theo cách không ai định nghĩa — chẳng hạn duyệt
toàn bộ thủ tục rồi đổ nguyên văn hàng chục điều luật ra màn hình. Danh mục các
dạng câu hỏi hợp lệ chặn đúng lớp lỗi đó, nên nó là một bản hợp đồng ràng buộc
chứ không phải tài liệu tham khảo.

Lỗi kỹ thuật thật — không nạp được mô hình, không đọc được mạng lưới — thì **không**
bị che thành "không có thông tin". Chúng được báo là lỗi hệ thống, vì che chúng
đi sẽ khiến sự cố hạ tầng trông giống như câu hỏi ngoài phạm vi.

## Thứ tự xây dựng, và vì sao không được đảo

```text
công văn chính thức → mạng lưới kiến thức → danh mục khả năng trả lời
                    → danh mục dạng câu hỏi → dữ liệu huấn luyện → mô hình
```

Chiều này là bắt buộc. **Không được viết câu hỏi trước rồi sửa mạng lưới cho
khớp** — làm vậy là để dữ liệu huấn luyện quyết định sự thật học vụ, trong khi
sự thật phải đến từ công văn.

Mỗi khả năng được đánh dấu hỗ trợ phải có một dạng câu hỏi tương ứng; mỗi dạng
câu hỏi phải có dữ liệu huấn luyện và dữ liệu đánh giá. Các kiểm tra tự động
xác nhận toàn bộ chuỗi ràng buộc này.

## Ghi vết

Mỗi lượt hỏi được ghi lại đầy đủ: câu gốc, câu đã chuẩn hoá, truy vấn mô hình
sinh ra nguyên văn, kết quả kiểm tra, số dòng dữ liệu và thời gian xử lý. Giao
diện chỉ hiển thị "Không có thông tin." nhưng bản ghi giữ nguyên nguyên nhân kỹ
thuật, nên luôn phân biệt được ba trường hợp: mô hình chủ động từ chối, mô hình
sinh sai, hay dữ liệu thiếu.

Phân biệt này quyết định việc sửa ở đâu: **truy vấn sai là lỗi mô hình hoặc dữ
liệu huấn luyện; truy vấn đúng nhưng dữ liệu sai là lỗi mạng lưới kiến thức.**

## Tài liệu liên quan

- [Ontology học vụ](ONTOLOGY.md) — mạng lưới kiến thức chứa gì và vì sao
- [Dataset](DATASET.md) — dữ liệu dạy mô hình dịch câu hỏi thành truy vấn
- [Kiến trúc phần mềm](ARCHITECTURE.md) — các thành phần và trách nhiệm
- [Đánh giá](EVALUATION.md) — đo bằng tiêu chí nào
