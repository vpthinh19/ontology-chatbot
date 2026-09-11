# Prompt deep research để bổ sung ontology

Bộ prompt dùng với Gemini Deep Research hoặc ChatGPT Deep Research để vét thông tin
học vụ và dịch vụ sinh viên của Trường Đại học Nha Trang mà ontology chưa có. Kết
quả là **hồ sơ đề xuất chờ người duyệt**, không phải dữ liệu nhập thẳng. Lý do chọn
các chủ đề nằm ở [`PIVOT-ASSESSMENT.md`](PIVOT-ASSESSMENT.md), mục 5.

## Cách dùng

1. Mỗi lượt chỉ làm **một chủ đề**. Dán [Prompt chung](#1-prompt-chung), điền ngày
   chốt, rồi dán **một** khối chủ đề ở [mục 2](#2-các-khối-chủ-đề) ngay bên dưới.
2. Nên chạy cùng một chủ đề trên cả hai công cụ (hai người chạy độc lập). Sau đó
   dùng [Prompt đối chiếu](#3-prompt-đối-chiếu-hai-kết-quả) để gộp và lộ chỗ lệch.
3. Đính kèm `resources/ontology/ontology.ttl` nếu công cụ cho phép. Không đính kèm
   cũng được: mỗi khối chủ đề đã ghi những gì ontology đang có.
4. Lưu khối JSON cuối báo cáo thành tệp `<mã-chủ-đề>-<gemini|chatgpt>-<YYYYMMDD>.json`.
   Lưu cả báo cáo chữ để người duyệt đọc lại.
5. Trước khi nhập, người duyệt làm theo [checklist ở mục 4](#4-checklist-duyệt-trước-khi-nhập).

Thứ tự ưu tiên được xếp theo câu hỏi người dùng thật và các câu "đồ thị không có"
trong phép đo toàn hệ thống: T01 → T12.

## 1. Prompt chung

````text
Bạn là nhà nghiên cứu dữ liệu học vụ. Nhiệm vụ: điều tra CHỦ ĐỀ ở cuối prompt tại
Trường Đại học Nha Trang (NTU) và lập hồ sơ bằng chứng để con người duyệt trước khi
nhập vào ontology của chatbot hỏi đáp cho sinh viên.

BỐI CẢNH
- Ontology phục vụ sinh viên đại học chính quy NTU. Nó lưu quy định và cách thực
  hiện CHUNG; không lưu dữ liệu của từng người.
- Ngày chốt nghiên cứu: [YYYY-MM-DD]. Chỉ dùng thông tin công bố đến ngày này.
- Khối chủ đề liệt kê những gì ontology ĐÃ CÓ. Chỉ kết luận "chưa có" dựa trên
  danh sách đó hoặc tệp ontology đính kèm, không dựa trên trí nhớ.

QUY TẮC NGUỒN
1. Ưu tiên trang và tệp chính thức thuộc tên miền ntu.edu.vn (kể cả tên miền con
   của phòng, trung tâm, khoa). Căn cứ pháp luật bên ngoài chỉ lấy từ cơ quan ban
   hành hoặc cổng văn bản pháp luật chính thức của Nhà nước.
2. Không dùng blog, mạng xã hội, trang tổng hợp, diễn đàn hay câu trả lời của AI
   làm bằng chứng. Chúng chỉ được dùng để tìm manh mối rồi đi tìm nguồn chính thức.
3. Mở và đọc chính trang hoặc tệp; không suy nội dung từ tiêu đề hay đoạn trích của
   kết quả tìm kiếm. Mọi URL phải là URL đã mở được trong phiên này; không đoán
   đường dẫn. Với biểu mẫu, ghi cả URL trang chứa lẫn URL tải tệp.
4. Ghi URL đầy đủ dạng văn bản. KHÔNG dùng ký hiệu trích dẫn nội bộ của công cụ
   (chẳng hạn "citeturn…", "[1]") vì chúng mất khi sao chép.
5. Phân biệt: văn bản còn hiệu lực; văn bản lịch sử; thông báo chỉ áp dụng cho một
   học kỳ/năm học/đợt; trang web không nêu thời hạn hiệu lực. Thông báo theo đợt
   ghi thành thông tin tạm thời có thời hạn, không khái quát thành quy định.
6. Hai nguồn nói khác nhau: không tự hòa giải. Ghi từng phát biểu, ngày, phạm vi
   và lý do nguồn nào nên được ưu tiên. Chỉ ưu tiên nguồn mới hơn khi phạm vi và
   thẩm quyền tương đương.
7. Không tự điền đơn vị phụ trách, thời hạn, lệ phí, điều kiện, biểu mẫu, thời gian
   xử lý hay kênh nộp. Nguồn không nói thì ghi "chưa tìm thấy trong nguồn chính
   thức đã kiểm tra".
8. Biểu mẫu không phải thủ tục: có tệp đơn không có nghĩa đã biết nơi nộp, trình
   tự, thời gian xử lý hay kết quả.
9. Tệp scan/ảnh: ghi rõ đã đọc bằng OCR; con số hay tên không đọc chắc thì ghi
   "không đọc được chắc chắn", không đoán.
10. Trang cần đăng nhập (ví dụ sinhvien.ntu.edu.vn): không cố truy cập; chỉ ghi
    chức năng được mô tả công khai ở nơi khác.

DỮ LIỆU CÁ NHÂN - TUYỆT ĐỐI KHÔNG THU THẬP
- Tên, mã số, ngày sinh, ảnh, số điện thoại hoặc email cá nhân của sinh viên hay
  cán bộ.
- Danh sách sinh viên trong quyết định học bổng, khen thưởng, kỷ luật, tốt nghiệp,
  miễn giảm. Chỉ lấy phần căn cứ, tiêu chí, mức và thời gian.
- Tên người đang giữ chức vụ. Chỉ ghi chức danh hoặc đơn vị.
Được ghi: số điện thoại, email, địa chỉ, giờ làm việc CHUNG của đơn vị.

CÔNG VIỆC
1. Tìm toàn bộ trang, quy trình, biểu mẫu, quyết định/quy định và thông báo còn
   liên quan trực tiếp tới chủ đề. Bắt đầu từ các URL xuất phát trong khối chủ đề,
   rồi mở rộng.
2. Với mỗi thủ tục hoặc dịch vụ, tái dựng các trường sau (trường nào nguồn không
   nói thì để trống kèm lý do):
   - tên chính và các tên gọi xuất hiện trong nguồn;
   - mục đích, đối tượng, hoàn cảnh phát sinh;
   - điều kiện, trường hợp không áp dụng;
   - giấy tờ cần nộp, tách biểu mẫu của Trường với giấy tờ minh chứng;
   - các bước theo đúng thứ tự; người/đơn vị làm từng bước;
   - nơi tiếp nhận, người quyết định;
   - kênh nộp (trực tiếp/trực tuyến/hệ thống nào, URL), địa điểm;
   - thời điểm nộp, thời gian xử lý, lệ phí;
   - kết quả nhận được, thời hạn giá trị, hệ quả, thủ tục tiếp theo;
   - ngoại lệ theo hệ đào tạo, khóa, ngành, học kỳ, nhóm sinh viên;
   - căn cứ của từng dữ kiện.
3. Đối chiếu với phần "Ontology đã có". Chia bốn loại: đã có và khớp; cần bổ
   sung/cập nhật; còn thiếu; chưa đủ bằng chứng.
4. Đề xuất bản ghi theo từ vựng bên dưới. Không viết Turtle, không đặt IRI mới
   (dùng mã tạm R1, R2…). Chỉ được trỏ tới IRI hiện có nếu nó nằm trong danh sách
   "Ontology đã có".

TỪ VỰNG CỦA ONTOLOGY (dùng tên lớp/thuộc tính đúng như dưới đây)
- AcademicProcedure (thủ tục): summaryText, hasStep, hasRequirement, hasDeadline,
  hasOutcome, hasConsequence, requiresForm, submittedTo, reviewedBy, decidedBy,
  nextProcedure
- ProcedureStep (bước): stepOrder, stepText, performedBy, submittedTo, usesForm
- Requirement (điều kiện): requirementOrder, requirementText
- Deadline (thời hạn): deadlineText | Outcome (kết quả): outcomeText |
  Consequence (hệ quả): consequenceText
- AcademicCase (trường hợp): caseText, hasResolution | CaseResolution:
  conditionText, resolvedBy
- FormDocument (biểu mẫu ban hành trong văn bản): formNumber
- FormCatalogueEntry (mục tải trên website): listedTitle, listedFormNumber,
  downloadUrl, catalogueEntryForForm
- OrganizationalUnit (đơn vị) / AcademicActor (vai trò): officeAddress,
  officeLocation, officePhone, officeEmail, officeWebsite
- AcademicPolicy (chính sách): summaryText | AcademicConcept (khái niệm):
  definitionText
- AcademicRule (quy tắc): ruleText, minimumCredits, maximumCredits,
  minimumPercentage, maximumPercentage, durationInYears
- AcademicProgram (ngành): belongsToDisciplineGroup | Certificate (chứng chỉ):
  officialCertificateName
- PaymentMethod: supportsBank | PaymentFeeRule: feeAmount, feePolicyText,
  appliesToPaymentMethod | ScholarshipRate: amount, currencyCode, billingUnit,
  criterionText
- Decision / Regulation / GuidanceDocument (văn bản, trang hướng dẫn):
  documentNumber, issueDate, title, documentUrl, webPageUrl, retrievedDate, amends
Nếu cần lớp hoặc thuộc tính chưa có, được đề xuất nhưng phải đánh dấu là mới.
Ví dụ lớp: OnlineSystem (hệ thống trực tuyến), Notice (thông báo theo đợt),
TuitionRate (mức học phí), SupportBenefit (chế độ hỗ trợ), StudentService (dịch vụ
như ký túc xá, thư viện). Ví dụ thuộc tính: openingHours, processingTime,
submissionChannel, validFrom, validUntil, appliesFromCohort, appliesToCohort.

ĐẦU RA BẮT BUỘC (tiếng Việt, theo đúng thứ tự)
A. Kết luận ngắn: phạm vi thực sự tìm được; hiện hành hay lịch sử; phần chưa kết
   luận được.
B. Bảng nguồn: ID | Tiêu đề | Loại | Số hiệu | Ngày ban hành/cập nhật | Ngày truy cập
   | URL | Hiệu lực.
C. Bảng bằng chứng, mỗi hàng MỘT phát biểu kiểm chứng được: ID | Phát biểu | Phạm vi
   áp dụng | Nguồn | Vị trí trong nguồn (điều/khoản/mục/trang) | Trích nguyên văn
   ngắn, tối đa 50 từ | Mức chắc chắn.
D. Hồ sơ nghiệp vụ chuẩn hóa theo các trường ở bước 2, sau mỗi trường ghi ID bằng
   chứng.
E. Xung đột và thiếu hụt: nguồn cũ/mới hoặc đơn vị nói khác nhau; URL hỏng, tệp
   không đọc được, hiệu lực không rõ; câu hỏi cần cán bộ Trường xác nhận; danh sách
   truy vấn tìm kiếm đã dùng.
F. MỘT khối ```json cuối cùng theo đúng khuôn sau (không thêm chú thích trong JSON):

{
  "chu_de": "",
  "ngay_chot": "YYYY-MM-DD",
  "cong_cu": "",
  "nguon": [
    {"id": "S1", "tieu_de": "", "loai": "quyet_dinh|quy_che|quy_dinh|huong_dan|thong_bao|trang_web|bieu_mau|van_ban_nha_nuoc",
     "so_hieu": "", "ngay_ban_hanh": "", "ngay_truy_cap": "", "url": "", "url_tep": "",
     "hieu_luc": "hien_hanh|lich_su|theo_dot|khong_ro", "ocr": false}
  ],
  "bang_chung": [
    {"id": "E1", "nguon": "S1", "vi_tri": "", "trich_nguyen_van": "", "phat_bieu": "",
     "muc_chac_chan": "cao|trung_binh|thap"}
  ],
  "ban_ghi": [
    {"tam_id": "R1", "lop": "AcademicProcedure", "lop_moi": false,
     "nhan": "",
     "ten_goi_trong_nguon": [],
     "ten_goi_de_xuat": [],
     "thuoc_tinh": {"summaryText": ""},
     "thuoc_tinh_moi": {},
     "quan_he": [{"thuoc_tinh": "hasStep", "den": "R2"},
                 {"thuoc_tinh": "submittedTo", "den": ":StudentAffairsOffice"}],
     "ap_dung": {"he_dao_tao": "", "tu_khoa": null, "den_khoa": null,
                 "hieu_luc_tu": "", "hieu_luc_den": ""},
     "trang_thai": "current|historical|temporary|uncertain",
     "doi_chieu": "moi|bo_sung|khop|mau_thuan",
     "iri_hien_co": "",
     "bang_chung": ["E1"]}
  ],
  "xung_dot": [{"mo_ta": "", "bang_chung": [], "de_xuat_uu_tien": ""}],
  "chua_tim_thay": [],
  "can_truong_xac_nhan": [],
  "truy_van_da_dung": []
}

Quy ước JSON:
- Mỗi giá trị trong "thuoc_tinh", "thuoc_tinh_moi" và "quan_he" phải có ít nhất một
  ID trong "bang_chung" của bản ghi đó.
- "nhan" là tên tự nhiên, không kèm tiền tố loại ("Thủ tục", "Mục tải:").
- "ten_goi_trong_nguon": tên xuất hiện trong nguồn. "ten_goi_de_xuat": cách sinh
  viên hay gọi (viết tắt, cách nói thường ngày). Mục này không phải dữ kiện, không
  cần bằng chứng, nhưng không được trùng tên của thứ khác.
- Bước và điều kiện là bản ghi riêng, có "stepOrder"/"requirementOrder"; không
  gộp nhiều bước vào một đoạn văn.
- Số tiền ghi dạng số nguyên đồng trong thuộc tính, kèm câu nguyên văn trong bằng
  chứng.

TỰ KIỂM TRƯỚC KHI KẾT THÚC
- Mọi dữ kiện nghiệp vụ có ít nhất một nguồn chính thức mở được.
- Không có dữ liệu cá nhân nào ở báo cáo và JSON.
- Không có biểu mẫu nào bị mô tả thành một quy trình hoàn chỉnh.
- Thông tin theo đợt đã được đánh dấu "temporary" kèm thời hạn.
- JSON hợp lệ và chỉ có một khối.

CHỦ ĐỀ:
````

## 2. Các khối chủ đề

Dán **một** khối dưới đây ngay sau dòng `CHỦ ĐỀ:` của Prompt chung.

### T01. Học phí: mức thu, thu nộp, gia hạn, nợ học phí

```text
[T01] Học phí đại học chính quy: mức thu hiện hành theo khối ngành/ngành/khóa, quy
trình thu, gia hạn, hệ quả khi chậm đóng, hoàn và rút học phí.

Ontology đã có:
- :TuitionPaymentProcedure (Thủ tục nộp học phí) cùng 3 bước "cách 1/2/3";
  4 phương thức thanh toán (:QRCodePayment, :MobileOrInternetBankingPayment,
  :VNPAYPayment, :CashAtBankCounterPayment); 6 quy tắc phí thanh toán; 3 ngân hàng
  (Agribank, VietinBank, Liên Việt PostBank); :TuitionLookupPage.
- Mức học phí HK I năm học 2025-2026 theo QĐ 729/QĐ-ĐHNT đã có trong tài liệu
  tham chiếu của nhóm, nhưng CHƯA nhập. Không cần nghiên cứu lại văn bản này, chỉ
  tìm văn bản thay thế hoặc cập nhật mới hơn.
- Chưa có: quy trình thu học phí, gia hạn, hệ quả chậm đóng, hoàn học phí, học phí
  học kỳ hè/học lại/cải thiện.

URL xuất phát:
- https://phongkhtc.ntu.edu.vn (mục "Văn bản - Quy trình, biểu mẫu", "Học phí")
- https://phongkhtc.ntu.edu.vn/tin-tuc/quy-dinh-moi-nhat-ve-muc-hoc-phi-tu-nam-hoc-2025---2026
- https://phongkhtc.ntu.edu.vn/thong-bao/thong-bao-ve-viec-dong-hoc-phi-hoc-ky-2--nam-hoc-2024-2025
- https://tuyensinh.ntu.edu.vn/de-an-tuyen-sinh/hoc-phi
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau ("Đơn xin gia hạn đóng học phí")

Cần tìm cụ thể:
- Quyết định mức học phí năm học 2026-2027 (nếu đã ban hành) và lộ trình tăng; cách
  áp dụng theo khóa (các mốc "áp dụng từ khóa ... trở về sau").
- QĐ 1314/QĐ-ĐHNT (28/08/2025) Quy trình thu học phí: bản chính thức, các bước, đơn
  vị, mốc thời gian.
- QĐ 1413/QĐ-ĐHNT (được thông báo học phí viện dẫn khi xử lý người không đóng đúng
  hạn): nội dung xử lý (cấm thi, xóa học phần...), hiệu lực.
- Gia hạn đóng học phí: đối tượng, hồ sơ, nơi nộp, hạn.
- Học phí học kỳ hè, học lại, học cải thiện; hoàn/rút học phí khi rút học phần hoặc
  thôi học; biên lai/hóa đơn điện tử.
- Hạn đóng từng học kỳ: chỉ ghi dạng "temporary" kèm học kỳ áp dụng.
```

### T02. Giấy xác nhận và giấy tờ hành chính cho sinh viên

```text
[T02] Các loại giấy xác nhận và giấy tờ sinh viên thường xin: xác nhận đang học, xác
nhận vay vốn, xác nhận để hưởng ưu đãi giáo dục, xác nhận hoãn nghĩa vụ quân sự,
giấy giới thiệu, xác nhận hộ khẩu/hoàn cảnh, bảng điểm, bản sao bằng, giấy chứng
nhận tốt nghiệp tạm thời, tra cứu văn bằng.

Ontology đã có:
- Không có thủ tục nào thuộc nhóm này.
- Có mục tải "Đơn xin cấp bản sao bằng" (:FormCatalogueEntry019) nhưng không có thủ
  tục đi kèm.
- Đơn vị: :StudentAffairsOffice (Phòng CTCT&SV), :AcademicManagementUnit (Phòng Đào
  tạo Đại học), :University.

URL xuất phát:
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau (các mục: "Đơn xác nhận
  đang học", "Hướng dẫn xác nhận đang học để hưởng ưu đãi", "Mẫu vay vốn", "Giấy
  giới thiệu", "Đơn xác nhận hộ khẩu thường trú trên 03 năm", "Đơn xác nhận hoàn
  cảnh khó khăn")
- https://phongctsv.ntu.edu.vn/lien-he
- https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy/quy-trinh-bieu-mau
- https://qldt.ntu.edu.vn/tracuuvanbangchungchi.html

Cần tìm cụ thể, cho TỪNG loại giấy:
- Đơn vị cấp; nộp trực tiếp hay trực tuyến (hệ thống nào); giấy tờ kèm; thời gian
  trả kết quả; lệ phí; số bản; mẫu đơn (URL tệp).
- Mẫu xác nhận theo quy định của Nhà nước (ví dụ mẫu xác nhận vay vốn, ưu đãi giáo
  dục, nghĩa vụ quân sự): căn cứ văn bản nhà nước còn hiệu lực.
- Cấp bảng điểm, bản sao bằng, giấy chứng nhận tốt nghiệp tạm thời: nơi nộp, lệ
  phí, thời gian.
```

### T03. Miễn giảm học phí, hỗ trợ chi phí học tập, trợ cấp và chính sách

```text
[T03] Chế độ chính sách tài chính cho sinh viên: miễn, giảm học phí; hỗ trợ chi phí
học tập; trợ cấp xã hội; chính sách cho sinh viên khuyết tật, dân tộc thiểu số, hộ
nghèo/cận nghèo; vay vốn tín dụng sinh viên.

Ontology đã có: không có gì thuộc nhóm này (chỉ có học bổng khuyến khích học tập,
xem :ScholarshipReviewProcedure, 6 mức :ScholarshipRate theo QĐ 317).

URL xuất phát:
- https://phongctsv.ntu.edu.vn/che-%C4%91o-chinh-sach
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau (các mục: "Đơn đề nghị
  miễn, giảm học phí (NĐ 238/2025)", "Đơn hỗ trợ chi phí học tập (hộ nghèo/cận
  nghèo) 2026", "Đơn xin hưởng trợ cấp xã hội (TT53 2025)", "Mẫu đơn chính sách cho
  SV khuyết tật", "Đơn đề nghị hỗ trợ học tập (SV dân tộc thiểu số)", "Mẫu vay vốn")
- Trang chủ https://phongctsv.ntu.edu.vn có thông báo nộp hồ sơ miễn giảm học phí,
  hỗ trợ chi phí học tập cho HK I năm học 2026-2027.

Cần tìm cụ thể, cho TỪNG chế độ:
- Văn bản nhà nước làm căn cứ (xác minh số hiệu đầy đủ, ngày, hiệu lực của các văn
  bản được ghi tắt trên biểu mẫu như "NĐ 238/2025", "TT53 2025"); văn bản thay thế.
- Đối tượng và điều kiện; mức hưởng; hồ sơ; nơi nộp; thời điểm nộp mỗi học kỳ
  (temporary); cách và thời điểm chi trả; thời hạn hưởng; trường hợp mất quyền hưởng.
- Quy trình của Trường: lập danh sách dự kiến, thời gian phản hồi, quyết định.
- Vay vốn tín dụng sinh viên: vai trò của Trường (xác nhận) và vai trò của ngân hàng
  chính sách; không mô tả chi tiết thủ tục của ngân hàng nếu không có nguồn chính
  thức.
```

### T04. Học vụ còn thiếu: điểm, thi, chuẩn đầu ra, thực tập, tốt nghiệp

```text
[T04] Các thủ tục và quy định học vụ chưa có trong ontology: phúc khảo/điều chỉnh
điểm, báo điểm bổ sung, bảo lưu học phần, học phần thay thế, học kỳ hè, chuẩn đầu ra
ngoại ngữ và tin học, thực tập, công tác và lễ tốt nghiệp, nhận bằng, giáo dục quốc
phòng - an ninh và thể chất, trao đổi sinh viên trong nước.

Ontology đã có (24 thủ tục): chuyển ngành, chuyển trường, công nhận kết quả và
chuyển đổi tín chỉ, học liên thông, nghỉ học tạm thời, nộp học phí, rút bớt học phần,
chuyển chương trình khi thuộc diện buộc thôi học, hoãn thi, học trở lại, miễn học/miễn
thi/cộng điểm thưởng, nghỉ ốm, xin phép nghỉ học, thôi học, xét tốt nghiệp, xét học
bổng KKHT, trao đổi sinh viên (chương trình trao đổi), học cùng lúc hai chương trình,
học cải thiện, học lại, đăng ký khối lượng học tập, đăng ký đồ án tốt nghiệp, mở thêm
lớp, xét tốt nghiệp sớm. Có bảng quy đổi chứng chỉ ngoại ngữ/tin học và danh mục học
phần ngoại ngữ theo QĐ 1052/1965.
Có mục tải nhưng CHƯA có thủ tục: "Phiếu điều chỉnh điểm", "Phiếu báo điểm bổ sung",
"Đơn xin bảo lưu học phần", "Đơn xin chuyển học phần thay thế trong CTĐT".

URL xuất phát:
- https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy. Theo danh mục trên trang, cần đọc:
  QĐ 244 (20/02/2025) sửa đổi quy định đào tạo ngoại ngữ; QĐ 782 (12/07/2023) quy
  định thực tập; QĐ 1286 (02/12/2021) hướng dẫn công tác tốt nghiệp; QĐ 1889
  (09/12/2025) trao đổi sinh viên trong nước; TB 94 (27/01/2026) điều chỉnh tổ chức
  thực hiện hoạt động đào tạo; QĐ 1552 (08/10/2025) chương trình giáo dục thể chất.
- https://pdtdaihoc.ntu.edu.vn/dai-hoc/chuan-dau-ra
- https://pdtdaihoc.ntu.edu.vn/dai-hoc/ke-hoach-dao-tao-nam-hoc
- https://pdtdaihoc.ntu.edu.vn/dai-hoc/sinh-vien-tot-nghiep
- https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy/quy-trinh-bieu-mau

Cần tìm cụ thể:
- Chuẩn đầu ra ngoại ngữ và tin học theo khóa và nhóm ngành: mức yêu cầu, chứng chỉ
  được chấp nhận, nộp chứng chỉ ở đâu, thời hạn, miễn học phần ngoại ngữ. Đối chiếu
  văn bản cũ/mới và phạm vi khóa.
- Phúc khảo, điều chỉnh điểm, báo điểm bổ sung: điều kiện, hạn, nơi nộp, kết quả.
- Bảo lưu học phần, học phần thay thế, học kỳ hè: điều kiện, quy trình.
- Thực tập: điều kiện, giấy giới thiệu, đánh giá, trách nhiệm các bên.
- Tốt nghiệp: đợt xét trong năm, lễ tốt nghiệp, nhận bằng và bảng điểm, ủy quyền
  nhận thay (chỉ quy định chung).
- Kế hoạch năm học (bắt đầu/kết thúc học kỳ, thi): chỉ ghi "temporary" kèm năm học.
- Nội dung TB 94/2026 thay đổi điều gì so với QĐ 1052.
```

### T05. Danh bạ đơn vị phục vụ sinh viên

```text
[T05] Các phòng, trung tâm, khoa/viện mà sinh viên thường phải liên hệ: việc từng đơn
vị giải quyết cho sinh viên và thông tin liên hệ chung.

Ontology đã có:
- Có liên hệ (địa chỉ, vị trí, điện thoại, email, website): :University, Phòng Công
  tác Chính trị và Sinh viên, Phòng Đào tạo Đại học.
- "Khoa hoặc viện đào tạo" và "Bộ môn" chỉ là khái niệm chung.
- Chưa có giờ làm việc của đơn vị nào.

URL xuất phát:
- https://phongtchc.ntu.edu.vn/to-chuc/cac-%C4%91on-vi
- https://ntu.edu.vn/sinh-vien/cac-%C4%91on-vi-ho-tro/phong-cong-tac-chinh-tri-va-sinh-vien
  (mục "Các đơn vị hỗ trợ")
- https://phongkhtc.ntu.edu.vn, https://phongcntt.ntu.edu.vn, https://thuvien.ntu.edu.vn,
  https://trungtampvth.ntu.edu.vn

Cần tìm cho mỗi đơn vị: tên chính thức, tên viết tắt dùng trong nguồn, loại (phòng/
trung tâm/khoa/viện), việc giải quyết cho sinh viên (liệt kê theo nguồn chức năng
nhiệm vụ), tòa nhà/phòng, điện thoại, email, website, giờ làm việc. Ưu tiên: Phòng
Kế hoạch - Tài chính, Phòng Công nghệ thông tin, Trung tâm Phục vụ trường học, Thư
viện/Trung tâm Thông tin - Tư liệu, Trung tâm Hỗ trợ việc làm và Khởi nghiệp, Phòng
Khảo thí/Đảm bảo chất lượng, Trung tâm Ngoại ngữ, Trạm y tế, Đoàn Thanh niên - Hội
Sinh viên, các khoa/viện đào tạo.
KHÔNG ghi tên, số điện thoại hay email cá nhân của cán bộ.
```

### T06. Bảo hiểm y tế, bảo hiểm tai nạn, chăm sóc sức khỏe

```text
[T06] Bảo hiểm y tế sinh viên, bảo hiểm tai nạn, khám sức khỏe đầu khóa, y tế trường.

Ontology đã có: không có gì thuộc nhóm này.

URL xuất phát: tìm trên https://phongctsv.ntu.edu.vn và https://ntu.edu.vn (thông báo
thu bảo hiểm y tế theo năm học), cùng văn bản của cơ quan bảo hiểm xã hội về BHYT
học sinh, sinh viên.

Cần tìm cụ thể:
- BHYT bắt buộc: căn cứ pháp luật hiện hành; mức đóng/năm và phần ngân sách hỗ trợ
  (ghi năm áp dụng); đợt và hạn thu (temporary); cách đóng; trường hợp đã có thẻ ở
  địa phương hoặc thuộc đối tượng được cấp thẻ (hồ sơ chứng minh); nơi đăng ký khám
  chữa bệnh ban đầu; cấp lại thẻ.
- Bảo hiểm tai nạn (nếu có): tự nguyện hay bắt buộc, mức phí, quyền lợi theo nguồn.
- Khám sức khỏe đầu khóa, trạm y tế trường: địa điểm, giờ, dịch vụ.
```

### T07. Tài khoản, email, hệ thống trực tuyến, thẻ sinh viên

```text
[T07] Hệ thống trực tuyến sinh viên dùng (cổng sinh viên, quản lý đào tạo, thanh toán
học phí, email, thư viện...), cách đăng nhập và khôi phục tài khoản, thẻ sinh viên.

Ontology đã có: :TuitionLookupPage (trang tra cứu học phí sinh viên). Chưa có hệ thống
nào khác, chưa có thẻ sinh viên.

URL xuất phát:
- https://phongcntt.ntu.edu.vn/uploads/4/files/HDSD%20DangNhap%20sinhvien.pdf
- https://daotao.ntu.edu.vn/1.Email.pdf
- https://account.ntu.edu.vn
- https://sinhvien.ntu.edu.vn, https://qldt.ntu.edu.vn, https://thuhocphi.ntu.edu.vn
  (chỉ ghi chức năng được mô tả công khai, không đăng nhập)
- https://thuvien.ntu.edu.vn

Cần tìm cụ thể:
- Mỗi hệ thống: tên, URL, dùng để làm gì, ai được cấp tài khoản, cách đăng nhập lần
  đầu và khôi phục mật khẩu theo hướng dẫn chính thức, đơn vị hỗ trợ.
- Email sinh viên: cấp khi nào, dùng cho việc gì, hỗ trợ khi mất truy cập.
- Thẻ sinh viên: cấp lần đầu, cấp lại khi mất/hỏng (hồ sơ, nơi nộp, lệ phí, thời
  gian), chức năng tích hợp (nếu nguồn nói).
```

### T08. Điểm rèn luyện, khen thưởng, kỷ luật

```text
[T08] Đánh giá kết quả rèn luyện của sinh viên, khen thưởng sinh viên, xử lý kỷ luật.

Ontology đã có: :AcademicMisconductPolicy (chính sách xử lý sinh viên vi phạm, theo
Quy chế đào tạo), :DisciplineHonoursPenalty (hạ hạng tốt nghiệp do bị kỷ luật). Chưa
có điểm rèn luyện, khen thưởng, quy trình kỷ luật.

URL xuất phát:
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau ("Mẫu phiếu đánh giá điểm
  rèn luyện", "Mẫu bản tường trình")
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau
- https://phongtchc.ntu.edu.vn/Uploads/42/VBHN-Quy%20che%20Thi%20dua,%20khen%20thuong%20(QD360-2022%20v%C3%A0%20QD764-2024).pdf

Cần tìm cụ thể:
- Văn bản của Bộ và của Trường về đánh giá kết quả rèn luyện còn hiệu lực.
- Tiêu chí, khung điểm, thang xếp loại; quy trình (tự đánh giá → lớp → cố vấn học
  tập → khoa/viện → hội đồng trường); thời điểm mỗi học kỳ; khiếu nại; nơi dùng kết
  quả (học bổng, khen thưởng, tốt nghiệp...).
- Khen thưởng sinh viên: danh hiệu, tiêu chuẩn, quy trình xét.
- Kỷ luật: hình thức, hành vi tương ứng, quy trình, quyền khiếu nại, xóa kỷ luật.
```

### T09. Ngành và chương trình đào tạo

```text
[T09] Thông tin ổn định của từng ngành đào tạo đại học chính quy.

Ontology đã có: 41 ngành, mỗi ngành chỉ có tên và khối ngành (theo Phụ lục II QĐ 729).
Chưa có mã ngành, đơn vị quản lý, số tín chỉ, thời gian đào tạo, loại chương trình,
chuẩn đầu ra.

URL xuất phát: https://ctdt.ntu.edu.vn/, https://pdtdaihoc.ntu.edu.vn/dai-hoc/chuan-dau-ra,
https://tuyensinh.ntu.edu.vn

Cần tìm cho mỗi ngành: mã ngành; khoa/viện quản lý; tổng số tín chỉ tối thiểu; thời
gian đào tạo chuẩn; các chương trình (chuẩn, đặc biệt, song ngữ, đạt kiểm định...);
URL chương trình đào tạo và chuẩn đầu ra; tên gọi tắt xuất hiện trong nguồn.
Điểm chuẩn, chỉ tiêu, tổ hợp xét tuyển thay đổi theo năm: KHÔNG ghi số, chỉ ghi URL
trang công bố chính thức.
```

### T10. Ký túc xá, thư viện, việc làm, hoạt động và đời sống sinh viên

```text
[T10] Dịch vụ đời sống: ký túc xá, ngoại trú, thư viện, hỗ trợ việc làm - khởi nghiệp,
Đoàn - Hội, gửi xe.

Ontology đã có: không có gì thuộc nhóm này.

URL xuất phát:
- https://trungtampvth.ntu.edu.vn/dich-vu/he-thong-ky-tuc-xa
- https://trungtampvth.ntu.edu.vn/Gioi-thieu/Co-so-vat-chat/Ky-tuc-xa
- https://thuvien.ntu.edu.vn
- https://ntu.edu.vn/sinh-vien/%C4%91oi-song-sinh-vien
- https://ntu.edu.vn/sinh-vien/cac-%C4%91on-vi-ho-tro/trung-tam-ho-tro-viec-lam-va-khoi-nghiep
- https://thanhnien.ntu.edu.vn/danh-muc/ho-tro-sinh-vien

Cần tìm cụ thể:
- Ký túc xá: khu nhà, đối tượng ưu tiên, cách và thời điểm đăng ký, giá phòng (ghi
  năm áp dụng, "temporary" nếu là thông báo), điều kiện ở tiếp, nội quy chính, liên hệ.
- Ngoại trú: nghĩa vụ khai báo nơi ở (nếu có quy định).
- Thư viện: giờ mở cửa, thẻ/tài khoản, mượn/trả, phòng tự học, tài nguyên số.
- Việc làm - khởi nghiệp: dịch vụ cho sinh viên, cách tiếp cận.
- Đoàn - Hội: xác nhận hoạt động/tình nguyện (nếu có quy trình).
- Gửi xe: nơi gửi, phí (ghi năm áp dụng).
```

### T11. Nhập học và tuần sinh hoạt công dân

```text
[T11] Thủ tục nhập học của tân sinh viên đại học chính quy và các việc đầu khóa.

Ontology đã có: :AdmissionsLookupPage (trang thông tin tuyển sinh), Quy chế tuyển sinh
theo QĐ 626. Chưa có thủ tục nhập học.

URL xuất phát: https://tuyensinh.ntu.edu.vn/nhap-hoc, https://tuyensinh.ntu.edu.vn

Cần tìm cụ thể: các bước xác nhận và làm thủ tục nhập học (trực tuyến/trực tiếp), hồ
sơ, khoản thu đầu khóa (ghi năm, "temporary"), sinh hoạt công dân đầu khóa, khám sức
khỏe, nhận thẻ/email/tài khoản ban đầu, bảo lưu kết quả trúng tuyển (nếu có quy định).
Chỉ ghi phần áp dụng chung; mốc ngày của từng đợt là "temporary".
```

### T12. Đối chiếu các bộ biểu mẫu

```text
[T12] Nhiệm vụ đối chiếu, không tìm chủ đề mới: lập bảng ánh xạ giữa các bộ biểu mẫu
đang cùng tồn tại và xác định bản nào đang dùng cho thủ tục nào.

Ontology đã có:
- 16 biểu mẫu ban hành trong văn bản (:FormDocument): Mẫu số 01-15 theo QĐ 1052 và
  "Mẫu số 2 - Phiếu đăng ký/điều chỉnh học phần" theo QĐ 753.
- 18 mục tải trên trang Phòng Đào tạo (:FormCatalogueEntry).
- Số thứ tự hai bộ không trùng. Ví dụ ontology có "Mẫu số 15 - Đơn đăng ký học cùng
  lúc hai chương trình" theo QĐ 1052, nhưng mục tải ghi "Mẫu số 13".

Nguồn cần đối chiếu:
- Phụ lục biểu mẫu của QĐ 1052/QĐ-ĐHNT và QĐ 1965/QĐ-ĐHNT (sửa đổi phụ lục).
- https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy/quy-trinh-bieu-mau
- https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau (bộ "Biểu mẫu 2026": đơn
  chuyển trường, chuyển ngành các trường hợp, nghỉ học tạm thời, thôi học, học lại,
  tiếp tục học).

Đầu ra thêm (trước khối JSON): bảng Tên đơn | Số theo QĐ 1052/1965 | Số/tiêu đề trên
trang Phòng Đào tạo | Tiêu đề trên trang Phòng CTCT&SV | Thủ tục tương ứng | URL tệp
từng nơi | Ngày cập nhật | Bản nên dùng hiện nay và căn cứ. Trong JSON, mỗi mục tải
là một bản ghi FormCatalogueEntry có "catalogueEntryForForm" trỏ tới biểu mẫu tương
ứng (IRI hiện có hoặc mã tạm).
```

## 3. Prompt đối chiếu hai kết quả

Dùng sau khi có hai tệp JSON của cùng một chủ đề từ hai công cụ. Chạy trên công cụ
có duyệt web để nó mở lại được URL.

```text
Bạn nhận hai hồ sơ JSON cùng chủ đề, do hai công cụ nghiên cứu độc lập tạo ra theo
cùng một khuôn. Nhiệm vụ: gộp thành MỘT hồ sơ theo đúng khuôn đó để con người duyệt.

Quy tắc:
1. Mở lại mọi URL trong "nguon". URL không mở được hoặc không chứa đoạn
   "trich_nguyen_van" tương ứng thì đánh dấu bằng chứng đó "khong_kiem_lai_duoc" và
   hạ "muc_chac_chan" xuống "thap".
2. Hai hồ sơ cùng khẳng định một dữ kiện và bằng chứng kiểm lại được: giữ một bản,
   gộp danh sách bằng chứng.
3. Hai hồ sơ nói khác nhau: KHÔNG chọn thay con người. Giữ cả hai giá trị, thêm một
   mục vào "xung_dot" nêu giá trị, nguồn, ngày, phạm vi của từng bên.
4. Dữ kiện chỉ một hồ sơ có: giữ, nhưng ghi "chi_mot_cong_cu": true trong bản ghi.
5. Gộp bản ghi trùng thực thể (cùng thủ tục/biểu mẫu/đơn vị) và đánh lại mã tạm; cập
   nhật mọi tham chiếu "den" cho khớp.
6. Xóa mọi dữ liệu cá nhân còn sót (tên, mã số, liên hệ cá nhân, danh sách sinh viên).
7. Không thêm dữ kiện mới không có trong hai hồ sơ, trừ khi vừa kiểm lại được trên
   nguồn chính thức; khi đó ghi rõ nguồn mới trong "nguon".

Đầu ra: (a) bảng tóm tắt số dữ kiện đồng thuận / chỉ một công cụ / xung đột / không
kiểm lại được; (b) danh sách xung đột cần người quyết; (c) MỘT khối JSON đã gộp.

HỒ SƠ 1:
[dán JSON]

HỒ SƠ 2:
[dán JSON]
```

## 4. Checklist duyệt trước khi nhập

- [ ] Mở ngẫu nhiên ít nhất 1/3 số URL trong `nguon`, và toàn bộ URL của các dữ
      kiện có số tiền, thời hạn hoặc điều kiện loại trừ.
- [ ] `trich_nguyen_van` có thật trong nguồn và đúng vị trí ghi.
- [ ] Hiệu lực: văn bản chưa bị thay thế; khóa hoặc hệ áp dụng đúng.
- [ ] Mục `temporary` có thời hạn; không có thông báo theo đợt nào bị ghi thành quy
      định chung.
- [ ] Không có dữ liệu cá nhân.
- [ ] Nhãn không kèm tiền tố loại; `ten_goi_de_xuat` không trùng tên thực thể khác
      trong ontology.
- [ ] Lớp hoặc thuộc tính mới (`lop_moi`, `thuoc_tinh_moi`) đã được thống nhất trong
      lược đồ trước khi nhập.
- [ ] Bản ghi vào ontology ở trạng thái `draft`, kèm tệp JSON gốc làm bằng chứng.
