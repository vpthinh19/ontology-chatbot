"""Xây bộ probe đối kháng: cùng ý định, nhiều sắc thái diễn đạt.

Bộ này KHÔNG tham gia huấn luyện và KHÔNG thay thế tập test. Nó đo một điều duy
nhất mà tập test hiện tại không đo được: model có giữ được cùng một truy vấn khi
người dùng đổi cách nói hay không.

Mười khuôn sắc thái (`pattern`) được áp cho mọi ô ngữ nghĩa:

    P01 formal-direct      câu hành chính đầy đủ
    P02 how-to             "làm sao để ..."
    P03 particle           "... sao vậy ạ" - trợ từ cuối câu
    P04 clipped            cụt lủn, không dấu câu
    P05 first-person       kể ở ngôi thứ nhất
    P06 situation          kể tình huống, KHÔNG gọi tên thủ tục
    P07 lead-in            "cho em hỏi ..."
    P08 no-diacritics      viết không dấu
    P09 teencode           viết tắt kiểu chat
    P10 deferential        nhờ vả lễ phép

P06 là nhóm khó nhất và cũng quan trọng nhất: người hỏi mô tả hoàn cảnh chứ
không biết tên thủ tục. Ontology phải đi từ tình huống tới thủ tục.
"""

from __future__ import annotations

import json
from pathlib import Path

PATTERNS = (
    "P01-formal-direct",
    "P02-how-to",
    "P03-particle",
    "P04-clipped",
    "P05-first-person",
    "P06-situation",
    "P07-lead-in",
    "P08-no-diacritics",
    "P09-teencode",
    "P10-deferential",
)

REGISTERS = (
    "formal",
    "neutral",
    "colloquial",
    "noisy",
    "neutral",
    "colloquial",
    "neutral",
    "noisy",
    "noisy",
    "formal",
)

# (intent, entity, [10 câu theo thứ tự P01..P10])
CELLS: list[tuple[str, str, list[str]]] = [
    # ---------------------------------------------------------------- thủ tục
    (
        "procedure-instruction",
        "TemporaryAcademicLeaveProcedure",
        [
            "Thủ tục xin nghỉ học tạm thời được thực hiện theo trình tự nào?",
            "Làm sao để bảo lưu kết quả học tập?",
            "Bảo lưu sao vậy ạ?",
            "bảo lưu kết quả kiểu gì",
            "Em muốn tạm dừng việc học một năm thì phải làm những gì?",
            "Em sắp phải lên đường nhập ngũ, giờ tính sao với việc học ạ?",
            "Cho em hỏi muốn giữ lại kết quả đã học rồi nghỉ một thời gian thì làm thế nào?",
            "lam sao de bao luu ket qua hoc tap",
            "bảo lưu ntn v ạ",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục nghỉ học tạm thời với ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "CourseRegistrationProcedure",
        [
            "Quy trình đăng ký khối lượng học tập từng học kỳ gồm những bước nào?",
            "Làm sao để đăng ký môn cho kỳ tới?",
            "Đăng ký lớp học phần thế nào vậy ạ?",
            "đk môn kiểu gì",
            "Em là sinh viên năm nhất, muốn chọn môn học thì bắt đầu từ đâu?",
            "Sắp vào kỳ mới rồi mà em chưa biết phải thao tác gì trên hệ thống cả.",
            "Cho hỏi cách chọn lớp cho học kỳ sau ạ.",
            "dang ky hoc phan can lam nhung buoc nao",
            "đky hp ntn ạ",
            "Mong thầy cô chỉ giúp em cách đăng ký khối lượng học tập.",
        ],
    ),
    (
        "procedure-instruction",
        "CourseRetakeProcedure",
        [
            "Sinh viên đăng ký học lại học phần chưa đạt theo trình tự nào?",
            "Làm sao để đăng ký học lại môn bị rớt?",
            "Thi trượt rồi thì đăng ký học lại kiểu gì ạ?",
            "học lại môn sao",
            "Em bị điểm F một học phần, giờ muốn học lại thì làm sao?",
            "Kỳ vừa rồi em có một môn không qua, giờ phải xử lý thế nào ạ?",
            "Cho em hỏi thủ tục đăng ký học lại học phần.",
            "muon hoc lai mon truot thi lam the nao",
            "hc lại mh ntn",
            "Kính mong thầy cô chỉ dẫn giúp em cách đăng ký học lại ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "GradeImprovementProcedure",
        [
            "Sinh viên đăng ký học cải thiện điểm theo quy định nào?",
            "Làm sao để học cải thiện điểm một học phần đã qua?",
            "Học cải thiện sao vậy ạ?",
            "cải thiện điểm sao",
            "Em qua môn rồi nhưng điểm thấp, muốn học lại cho cao hơn thì làm gì?",
            "Môn đó em được D, muốn kéo điểm lên thì có cách nào không ạ?",
            "Cho em hỏi cách đăng ký học cải thiện điểm.",
            "muon hoc cai thien diem thi lam sao",
            "cải thiện đ ntn ạ",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục học cải thiện điểm.",
        ],
    ),
    (
        "procedure-instruction",
        "MajorChangeProcedure",
        [
            "Thủ tục xin chuyển ngành đào tạo được thực hiện như thế nào?",
            "Làm sao để chuyển sang ngành khác?",
            "Chuyển ngành sao vậy ạ?",
            "đổi ngành kiểu gì",
            "Em thấy không hợp với ngành đang học, muốn đổi ngành thì làm sao?",
            "Học được một năm rồi em thấy mình chọn sai ngành, giờ phải làm gì ạ?",
            "Cho em hỏi trình tự xin chuyển ngành.",
            "muon chuyen nganh thi lam nhung gi",
            "chuyển ngành ntn v",
            "Kính nhờ thầy cô hướng dẫn giúp em thủ tục chuyển ngành ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "StudyWithdrawalProcedure",
        [
            "Sinh viên xin thôi học cần thực hiện những thủ tục nào?",
            "Làm sao để xin thôi học?",
            "Thôi học sao vậy ạ?",
            "nghỉ hẳn sao",
            "Em quyết định không học tiếp nữa thì phải làm thủ tục gì?",
            "Em muốn dừng hẳn việc học ở trường, không quay lại nữa thì sao ạ?",
            "Cho em hỏi thủ tục xin nghỉ học luôn.",
            "xin thoi hoc can lam gi",
            "thôi hc ntn ạ",
            "Mong nhà trường hướng dẫn giúp em thủ tục xin thôi học.",
        ],
    ),
    (
        "procedure-instruction",
        "StudyResumptionProcedure",
        [
            "Sinh viên hết thời gian nghỉ học tạm thời muốn trở lại học phải làm gì?",
            "Làm sao để quay lại học sau khi bảo lưu?",
            "Đi học lại sau bảo lưu sao vậy ạ?",
            "trở lại học kiểu gì",
            "Em bảo lưu xong rồi, giờ muốn vào học tiếp thì làm thủ tục gì?",
            "Em nghỉ tạm hai học kỳ, sang kỳ tới muốn đi học bình thường lại ạ.",
            "Cho em hỏi cách xin nhập học trở lại.",
            "nghi tam xong roi gio vao hoc tiep the nao",
            "quay lại hc sau bl ntn",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục trở lại học tập ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "ExamPostponementProcedure",
        [
            "Thủ tục xin hoãn thi kết thúc học phần được quy định thế nào?",
            "Làm sao để xin hoãn thi?",
            "Hoãn thi sao vậy ạ?",
            "xin hoãn thi sao",
            "Em bị ốm đúng hôm thi, muốn thi vào đợt sau thì làm gì?",
            "Đúng ngày thi em có việc gia đình đột xuất không đi được, giờ sao ạ?",
            "Cho em hỏi thủ tục xin lùi lịch thi.",
            "muon xin hoan thi thi lam the nao",
            "hoãn thi ntn v ạ",
            "Kính mong thầy cô hướng dẫn giúp em thủ tục xin hoãn thi.",
        ],
    ),
    (
        "procedure-instruction",
        "SickLeaveProcedure",
        [
            "Sinh viên nghỉ ốm trong quá trình học phải thực hiện thủ tục nào?",
            "Làm sao để xin nghỉ ốm?",
            "Nghỉ ốm sao vậy ạ?",
            "xin nghỉ ốm sao",
            "Em bị sốt phải nằm viện mấy hôm, muốn xin phép nghỉ thì làm gì?",
            "Em nằm viện gần hai tuần nay, không lên lớp được buổi nào ạ.",
            "Cho em hỏi thủ tục xin nghỉ vì lý do sức khỏe.",
            "bi om muon xin nghi hoc thi lam sao",
            "nghỉ ốm ntn ạ",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục xin nghỉ ốm với ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "CreditRecognitionProcedure",
        [
            "Thủ tục công nhận kết quả học tập và chuyển đổi tín chỉ gồm những bước nào?",
            "Làm sao để được công nhận tín chỉ đã học?",
            "Chuyển đổi tín chỉ sao vậy ạ?",
            "công nhận tín chỉ kiểu gì",
            "Em học ở trường cũ một số môn, muốn được tính sang đây thì làm sao?",
            "Mấy môn em học bên trường trước có được tính lại không, làm thế nào ạ?",
            "Cho em hỏi thủ tục xin công nhận các học phần đã tích lũy.",
            "muon chuyen doi tin chi da hoc thi lam gi",
            "cn tín chỉ ntn ạ",
            "Kính nhờ thầy cô hướng dẫn thủ tục công nhận và chuyển đổi tín chỉ ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "SecondProgramRegistrationProcedure",
        [
            "Sinh viên đăng ký học cùng lúc hai chương trình theo trình tự nào?",
            "Làm sao để học thêm một ngành thứ hai?",
            "Học song ngành sao vậy ạ?",
            "học 2 ngành kiểu gì",
            "Em muốn học thêm một bằng nữa song song thì phải làm gì?",
            "Em thấy sức mình học được nhiều hơn, muốn lấy thêm một tấm bằng nữa ạ.",
            "Cho em hỏi thủ tục đăng ký chương trình thứ hai.",
            "muon hoc cung luc hai chuong trinh thi lam sao",
            "học song bằng ntn v",
            "Mong thầy cô hướng dẫn giúp em thủ tục học cùng lúc hai chương trình.",
        ],
    ),
    (
        "procedure-instruction",
        "UniversityTransferProcedure",
        [
            "Thủ tục chuyển trường được nhà trường quy định như thế nào?",
            "Làm sao để chuyển sang trường khác?",
            "Chuyển trường sao vậy ạ?",
            "chuyển trường kiểu gì",
            "Gia đình em chuyển vào Nam, em muốn chuyển trường theo thì làm gì?",
            "Nhà em vừa chuyển đi tỉnh khác, em không tiện học ở đây nữa ạ.",
            "Cho em hỏi thủ tục xin chuyển sang trường khác.",
            "muon chuyen truong thi can lam nhung gi",
            "chuyển trg ntn ạ",
            "Kính mong nhà trường hướng dẫn giúp em thủ tục chuyển trường.",
        ],
    ),
    (
        "procedure-instruction",
        "ArticulationStudyProcedure",
        [
            "Quy định về học liên thông được thực hiện theo trình tự nào?",
            "Làm sao để học liên thông lên đại học?",
            "Liên thông sao vậy ạ?",
            "học liên thông kiểu gì",
            "Em tốt nghiệp cao đẳng rồi, muốn học tiếp lên thì làm sao?",
            "Em có bằng cao đẳng, giờ muốn học tiếp cho có bằng đại học ạ.",
            "Cho em hỏi thủ tục học liên thông.",
            "muon hoc lien thong thi lam the nao",
            "liên thông ntn v ạ",
            "Nhờ thầy cô hướng dẫn giúp em quy định về học liên thông ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "GraduationProjectRegistrationProcedure",
        [
            "Thủ tục đăng ký thực hiện đồ án tốt nghiệp được quy định ra sao?",
            "Làm sao để đăng ký làm khóa luận tốt nghiệp?",
            "Đăng ký đồ án tốt nghiệp sao vậy ạ?",
            "đăng ký khóa luận sao",
            "Em sắp ra trường, muốn làm đồ án thay vì học chuyên đề thì làm gì?",
            "Năm cuối rồi, em muốn được giao đề tài để làm ạ.",
            "Cho em hỏi thủ tục đăng ký đồ án và khóa luận tốt nghiệp.",
            "dang ky lam do an tot nghiep the nao",
            "đăng ký đatn ntn ạ",
            "Kính nhờ thầy cô hướng dẫn thủ tục đăng ký đồ án tốt nghiệp ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "StudentExchangeProcedure",
        [
            "Thủ tục trao đổi sinh viên và công nhận tín chỉ được thực hiện thế nào?",
            "Làm sao để đi trao đổi sinh viên?",
            "Đi trao đổi sao vậy ạ?",
            "trao đổi sinh viên kiểu gì",
            "Em muốn sang trường đối tác học một kỳ thì phải làm gì?",
            "Em nghe nói có chương trình học một học kỳ ở trường khác, em quan tâm ạ.",
            "Cho em hỏi thủ tục tham gia chương trình trao đổi.",
            "muon di trao doi sinh vien thi lam sao",
            "đi trao đổi ntn v",
            "Mong thầy cô hướng dẫn giúp em thủ tục trao đổi sinh viên ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "ClassAbsenceRequestProcedure",
        [
            "Sinh viên xin phép nghỉ buổi học phải thực hiện thủ tục nào?",
            "Làm sao để xin nghỉ một buổi học?",
            "Xin nghỉ buổi học sao vậy ạ?",
            "xin vắng buổi học sao",
            "Em có việc bận một hôm, muốn xin phép vắng mặt thì làm gì?",
            "Mai em phải về quê có việc, không lên lớp được ạ.",
            "Cho em hỏi cách xin phép nghỉ tiết.",
            "muon xin nghi mot buoi hoc thi lam the nao",
            "xin nghỉ buổi hc ntn",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục xin phép nghỉ học ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "ExtraClassOpeningRequestProcedure",
        [
            "Thủ tục đề nghị mở thêm lớp học phần được quy định như thế nào?",
            "Làm sao để xin mở thêm một lớp học phần?",
            "Xin mở lớp sao vậy ạ?",
            "mở thêm lớp kiểu gì",
            "Môn em cần học kỳ này không có lớp nào mở, em muốn đề nghị mở thì làm sao?",
            "Cả nhóm em đều cần môn đó mà kỳ này trường không tổ chức lớp ạ.",
            "Cho em hỏi thủ tục xin mở thêm lớp học phần.",
            "muon de nghi mo them lop hoc phan thi lam gi",
            "xin mở lớp hp ntn ạ",
            "Kính mong thầy cô hướng dẫn thủ tục đề nghị mở lớp học phần ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "EarlyGraduationReviewProcedure",
        [
            "Thủ tục xét tốt nghiệp sớm được nhà trường quy định thế nào?",
            "Làm sao để được xét tốt nghiệp trước thời hạn?",
            "Ra trường sớm sao vậy ạ?",
            "tốt nghiệp sớm kiểu gì",
            "Em học vượt và đã đủ tín chỉ, muốn ra trường sớm thì làm gì?",
            "Em tích lũy đủ hết rồi mà còn một kỳ nữa mới tới hạn, có cách nào không ạ?",
            "Cho em hỏi thủ tục xin xét tốt nghiệp sớm.",
            "ra truong som can lam nhung thu tuc gi",
            "tn sớm ntn v ạ",
            "Nhờ thầy cô hướng dẫn giúp em thủ tục xét tốt nghiệp trước hạn ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "TuitionPaymentProcedure",
        [
            "Sinh viên thực hiện việc nộp học phí theo hướng dẫn nào?",
            "Làm sao để đóng học phí?",
            "Đóng học phí sao vậy ạ?",
            "nộp tiền học kiểu gì",
            "Em mới vào trường, chưa biết đóng tiền học ở đâu và bằng cách nào.",
            "Tới hạn nộp tiền rồi mà em chưa rõ phải làm thế nào ạ.",
            "Cho em hỏi cách thanh toán học phí.",
            "nop tien hoc theo nhung kenh nao",
            "đóng hp ntn ạ",
            "Kính nhờ nhà trường hướng dẫn giúp em cách nộp học phí ạ.",
        ],
    ),
    (
        "procedure-instruction",
        "CourseExemptionAndBonusProcedure",
        [
            "Thủ tục xét miễn học phần và cộng điểm thưởng được quy định ra sao?",
            "Làm sao để được miễn học một học phần?",
            "Xin miễn học phần sao vậy ạ?",
            "miễn môn kiểu gì",
            "Em có chứng chỉ tiếng Anh quốc tế, muốn xin miễn môn tiếng Anh thì làm gì?",
            "Em thi được IELTS rồi, không muốn học lại mấy môn ngoại ngữ nữa ạ.",
            "Cho em hỏi thủ tục xin miễn học phần và cộng điểm.",
            "muon xin mien hoc phan thi lam sao",
            "xin miễn hp ntn v",
            "Mong thầy cô hướng dẫn giúp em thủ tục xét miễn học phần ạ.",
        ],
    ),
    # ------------------------------------------------- đơn vị nhận hồ sơ
    (
        "procedure-submission-office",
        "TemporaryAcademicLeaveProcedure",
        [
            "Hồ sơ xin nghỉ học tạm thời được nộp tại đơn vị nào?",
            "Nộp đơn bảo lưu ở đâu?",
            "Đơn bảo lưu nộp chỗ nào vậy ạ?",
            "bảo lưu nộp đâu",
            "Em viết đơn bảo lưu xong rồi thì mang tới phòng nào?",
            "Em có đơn xin tạm dừng học rồi mà chưa biết đưa cho ai ạ.",
            "Cho em hỏi đơn nghỉ học tạm thời nộp tại phòng nào.",
            "don bao luu nop o dau",
            "nộp đơn bl ở phòng nào v",
            "Kính hỏi nhà trường, đơn xin nghỉ học tạm thời nộp ở đâu ạ?",
        ],
    ),
    (
        "procedure-submission-office",
        "MajorChangeProcedure",
        [
            "Đơn xin chuyển ngành được nộp tại đơn vị nào của trường?",
            "Nộp đơn chuyển ngành ở đâu?",
            "Đơn đổi ngành nộp chỗ nào vậy ạ?",
            "chuyển ngành nộp đâu",
            "Em làm xong đơn chuyển ngành rồi thì gửi tới bộ phận nào?",
            "Em điền đơn đổi ngành xong mà không biết đưa ở đâu ạ.",
            "Cho em hỏi đơn xin chuyển ngành nộp tại phòng nào.",
            "don xin chuyen nganh nop o dau",
            "đơn chuyển ngành nộp phòng nào ạ",
            "Kính hỏi đơn xin chuyển ngành được tiếp nhận tại đơn vị nào ạ?",
        ],
    ),
    (
        "procedure-submission-office",
        "ExamPostponementProcedure",
        [
            "Đơn xin hoãn thi được nộp tại đơn vị nào?",
            "Nộp đơn hoãn thi ở đâu?",
            "Đơn hoãn thi nộp chỗ nào vậy ạ?",
            "hoãn thi nộp đâu",
            "Em viết đơn xin hoãn thi rồi thì nộp cho phòng nào?",
            "Em có giấy của bệnh viện và đơn rồi mà chưa biết mang tới đâu ạ.",
            "Cho em hỏi đơn xin lùi lịch thi nộp tại đâu.",
            "don hoan thi nop cho phong nao",
            "đơn hoãn thi nộp ở đâu v ạ",
            "Kính hỏi đơn xin hoãn thi được nộp tại đơn vị nào ạ?",
        ],
    ),
    # ------------------------------------------------------- biểu mẫu
    (
        "procedure-required-form",
        "TemporaryAcademicLeaveProcedure",
        [
            "Thủ tục nghỉ học tạm thời yêu cầu sử dụng biểu mẫu nào?",
            "Làm sao biết bảo lưu dùng mẫu đơn số mấy?",
            "Bảo lưu xài mẫu nào vậy ạ?",
            "bảo lưu mẫu số mấy",
            "Em cần tải mẫu đơn để xin nghỉ học tạm thời, đó là mẫu nào?",
            "Em muốn in đơn ra điền mà không biết lấy tờ nào ạ.",
            "Cho em hỏi biểu mẫu dùng cho thủ tục bảo lưu.",
            "bao luu dung mau don nao",
            "mẫu đơn bl là mẫu mấy ạ",
            "Kính hỏi thủ tục nghỉ học tạm thời sử dụng mẫu đơn nào ạ?",
        ],
    ),
    (
        "procedure-required-form",
        "StudyResumptionProcedure",
        [
            "Thủ tục trở lại học tập yêu cầu biểu mẫu nào?",
            "Làm sao biết xin học lại sau bảo lưu dùng mẫu nào?",
            "Đi học lại xài mẫu đơn nào vậy ạ?",
            "trở lại học mẫu số mấy",
            "Em hết hạn bảo lưu muốn vào học lại, cần dùng mẫu đơn nào?",
            "Em chuẩn bị quay lại trường mà chưa biết phải điền tờ khai nào ạ.",
            "Cho em hỏi biểu mẫu xin nhập học trở lại.",
            "xin di hoc lai dung mau don so may",
            "mẫu đơn quay lại hc là mẫu nào ạ",
            "Kính hỏi thủ tục trở lại học tập sử dụng biểu mẫu nào ạ?",
        ],
    ),
    # ------------------------------------------------------- điều kiện
    (
        "procedure-eligibility",
        "TemporaryAcademicLeaveProcedure",
        [
            "Điều kiện để sinh viên được nghỉ học tạm thời là gì?",
            "Làm sao biết mình có đủ điều kiện bảo lưu hay không?",
            "Bảo lưu cần điều kiện gì vậy ạ?",
            "điều kiện bảo lưu",
            "Em mới học một kỳ thôi thì có được bảo lưu không?",
            "Không biết trường hợp của em có thuộc diện được tạm dừng học không ạ.",
            "Cho em hỏi các trường hợp được nghỉ học tạm thời.",
            "dieu kien de duoc bao luu la gi",
            "đk bảo lưu là gì ạ",
            "Kính hỏi sinh viên cần đáp ứng điều kiện nào để được nghỉ học tạm thời ạ?",
        ],
    ),
    (
        "procedure-eligibility",
        "MajorChangeProcedure",
        [
            "Điều kiện để sinh viên được xét chuyển ngành là gì?",
            "Làm sao biết mình đủ điều kiện chuyển ngành?",
            "Chuyển ngành cần điều kiện gì vậy ạ?",
            "điều kiện chuyển ngành",
            "Điểm của em hơi thấp thì có được xét đổi ngành không?",
            "Em không rõ trường hợp của em có được xem xét đổi ngành hay không ạ.",
            "Cho em hỏi yêu cầu để được chuyển ngành.",
            "dieu kien chuyen nganh gom nhung gi",
            "đk chuyển ngành ntn ạ",
            "Kính hỏi sinh viên phải thỏa mãn điều kiện nào mới được chuyển ngành ạ?",
        ],
    ),
    (
        "procedure-eligibility",
        "SecondProgramRegistrationProcedure",
        [
            "Sinh viên phải đáp ứng những yêu cầu nào mới được đăng ký chương trình thứ hai?",
            "Làm sao biết mình đủ điều kiện học song ngành?",
            "Học hai chương trình cần điều kiện gì vậy ạ?",
            "điều kiện học song bằng",
            "Em đang học năm hai, học lực khá thì có được đăng ký ngành hai không?",
            "Em muốn lấy thêm bằng nữa mà không rõ mình có đủ tiêu chuẩn không ạ.",
            "Cho em hỏi yêu cầu để đăng ký chương trình thứ hai.",
            "dieu kien hoc cung luc hai chuong trinh",
            "đk học 2 ngành là gì ạ",
            "Kính hỏi điều kiện đăng ký học cùng lúc hai chương trình là gì ạ?",
        ],
    ),
    # ------------------------------------------------------- thời hạn
    (
        "procedure-deadline",
        "StudyResumptionProcedure",
        [
            "Thời hạn nộp đơn xin trở lại học tập được quy định thế nào?",
            "Làm sao biết phải nộp đơn đi học lại trước bao lâu?",
            "Xin học lại phải nộp trước mấy tuần vậy ạ?",
            "trở lại học nộp trước bao lâu",
            "Em định kỳ sau đi học lại thì phải nộp đơn sớm bao nhiêu?",
            "Em sợ nộp muộn quá thì không kịp vào kỳ mới ạ.",
            "Cho em hỏi hạn nộp đơn xin nhập học trở lại.",
            "nop don di hoc lai truoc bao lau",
            "hạn nộp đơn quay lại hc ntn ạ",
            "Kính hỏi đơn xin trở lại học tập phải nộp trước thời điểm nào ạ?",
        ],
    ),
    (
        "procedure-deadline",
        "MajorChangeProcedure",
        [
            "Thời hạn nộp đơn xin chuyển ngành được quy định ra sao?",
            "Làm sao biết phải nộp đơn chuyển ngành trước bao lâu?",
            "Chuyển ngành nộp đơn trước mấy tuần vậy ạ?",
            "chuyển ngành hạn nộp khi nào",
            "Em muốn đổi ngành từ kỳ sau thì phải nộp đơn sớm cỡ nào?",
            "Em sợ để sát ngày quá thì không kịp xét ạ.",
            "Cho em hỏi thời hạn nộp hồ sơ chuyển ngành.",
            "nop don chuyen nganh truoc bao lau",
            "hạn nộp đơn chuyển ngành ntn ạ",
            "Kính hỏi đơn xin chuyển ngành phải nộp trước thời hạn nào ạ?",
        ],
    ),
    # --------------------------------------------- ngoài thủ tục: học phí
    (
        "tuition-program-cohort-rate",
        "InformationTechnology-K65",
        [
            "Mức học phí đối với sinh viên khóa 65 ngành Công nghệ thông tin là bao nhiêu?",
            "Làm sao biết học phí ngành Công nghệ thông tin khóa 65?",
            "Học phí K65 công nghệ thông tin bao nhiêu vậy ạ?",
            "hp k65 cntt bao nhiêu",
            "Em là sinh viên khóa 65 ngành Công nghệ thông tin, một tín chỉ bao nhiêu tiền?",
            "Em vào trường năm khóa 65, học ngành máy tính, không rõ đóng bao nhiêu ạ.",
            "Cho em hỏi mức thu học phí ngành Công nghệ thông tin khóa 65.",
            "hoc phi khoa 65 nganh cong nghe thong tin la bao nhieu",
            "1 tc ngành cntt k65 bn tiền ạ",
            "Kính hỏi mức học phí áp dụng cho khóa 65 ngành Công nghệ thông tin ạ?",
        ],
    ),
    (
        "payment-method-list",
        "TuitionPaymentProcedure",
        [
            "Việc thu học phí được thực hiện qua những kênh thanh toán nào?",
            "Làm sao biết có mấy cách đóng học phí?",
            "Có những kiểu đóng tiền học nào vậy ạ?",
            "đóng học phí bằng cách nào được",
            "Em muốn biết mình có thể trả học phí qua những hình thức nào.",
            "Em không tiện ra ngân hàng, không biết còn cách nào khác không ạ.",
            "Cho em hỏi các hình thức nộp học phí được chấp nhận.",
            "co nhung phuong thuc thanh toan hoc phi nao",
            "mấy cách đóng hp v ạ",
            "Kính hỏi sinh viên có thể lựa chọn những cách thức nộp học phí nào ạ?",
        ],
    ),
    (
        "academic-performance-band",
        "score-7.50",
        [
            "Sinh viên có điểm trung bình 7,50 được xếp loại học lực nào?",
            "Làm sao biết 7.50 thì xếp loại học lực gì?",
            "7.5 là học lực gì vậy ạ?",
            "gpa 7.5 loại gì",
            "Kỳ này em được 7,50 thì học lực của em xếp vào mức nào?",
            "Bảng điểm em ghi trung bình 7,50, không biết như vậy là khá hay giỏi ạ.",
            "Cho em hỏi điểm trung bình 7,50 xếp loại học lực ra sao.",
            "diem trung binh 7.50 xep loai hoc luc nao",
            "đtb 7.5 xếp loại j ạ",
            "Kính hỏi sinh viên đạt điểm trung bình 7,50 được xếp loại học lực nào ạ?",
        ],
    ),
    (
        "graduation-classification-band",
        "score-8.20",
        [
            "Sinh viên tốt nghiệp với điểm trung bình tích lũy 8,20 được xếp loại nào?",
            "Làm sao biết 8.20 thì tốt nghiệp loại gì?",
            "8.2 ra trường loại gì vậy ạ?",
            "cpa 8.2 tốt nghiệp loại nào",
            "Em tích lũy được 8,20 thì bằng của em xếp loại gì?",
            "Sắp ra trường rồi, điểm em 8,20 không biết ghi trên bằng là loại nào ạ.",
            "Cho em hỏi điểm 8,20 thì phân loại tốt nghiệp thế nào.",
            "diem tich luy 8.20 tot nghiep loai gi",
            "cpa 8.2 xếp loại tn j ạ",
            "Kính hỏi điểm trung bình tích lũy 8,20 được phân loại tốt nghiệp ra sao ạ?",
        ],
    ),
    (
        "form-list",
        "FormCatalogue",
        [
            "Nhà trường ban hành những biểu mẫu nào dành cho sinh viên?",
            "Làm sao biết trường có những mẫu đơn gì?",
            "Trường có mấy loại đơn vậy ạ?",
            "danh sách biểu mẫu",
            "Em muốn xem toàn bộ các mẫu đơn hiện có của trường.",
            "Em cần tìm một tờ khai nhưng không biết trường có sẵn những gì ạ.",
            "Cho em hỏi danh mục biểu mẫu của trường.",
            "truong co nhung bieu mau nao",
            "ds mẫu đơn của trg ạ",
            "Kính hỏi nhà trường có những biểu mẫu nào dành cho sinh viên ạ?",
        ],
    ),
    # ------------------------------------------- ngoài miền / gần miền
    (
        "no-information",
        "off-topic",
        [
            "Xin cho biết dự báo thời tiết tại Nha Trang vào cuối tuần này.",
            "Làm sao để nấu bún chả ngon?",
            "Trận đấu tối nay mấy giờ vậy ạ?",
            "giá vàng hôm nay",
            "Em muốn tìm phòng trọ gần trường, có chỗ nào rẻ không?",
            "Dạo này em thấy hơi chán, không biết nên làm gì cho vui.",
            "Cho em hỏi đường ra bãi biển gần nhất.",
            "may bay tu ha noi vao nha trang bao nhieu tien",
            "qtv ơi cho hỏi wifi trường pass gì ạ",
            "Kính nhờ tư vấn giúp em nên mua điện thoại hãng nào ạ.",
        ],
    ),
    (
        "no-information",
        "near-domain-missing-data",
        [
            "Đề nghị cho biết số điện thoại trực tiếp của giảng viên phụ trách học phần.",
            "Làm sao để biết điểm thi cuối kỳ của em môn Toán?",
            "Lớp em kỳ này học phòng nào vậy ạ?",
            "thời khóa biểu tuần sau của em",
            "Em muốn biết cố vấn học tập của lớp em tên gì.",
            "Em quên mất mã sinh viên của mình rồi ạ.",
            "Cho em hỏi kết quả xét học bổng kỳ vừa rồi.",
            "cho em xin diem ren luyen hoc ky nay",
            "lịch thi lại của e khi nào ạ",
            "Kính hỏi danh sách sinh viên lớp em gồm những ai ạ?",
        ],
    ),
    (
        "no-information",
        "hard-negative",
        [
            "Đề nghị cho biết mức lương khởi điểm của sinh viên ngành Công nghệ thông tin sau tốt nghiệp.",
            "Làm sao để xin học bổng du học sau khi tốt nghiệp ở đây?",
            "Trường mình có ký túc xá cho sinh viên năm nhất không ạ?",
            "học phí trường đại học nha trang so với bách khoa",
            "Em muốn biết điểm chuẩn ngành Công nghệ thông tin năm nay là bao nhiêu.",
            "Em đang phân vân giữa ngành Kế toán và Kiểm toán, ngành nào dễ xin việc hơn ạ?",
            "Cho em hỏi trường có chương trình liên kết với đại học nước ngoài không.",
            "truong co bao nhieu sinh vien dang theo hoc",
            "trg mình có clb gì hay ko ạ",
            "Kính hỏi nhà trường có tổ chức đưa đón sinh viên bằng xe buýt không ạ?",
        ],
    ),
    (
        "no-information",
        "mixed-query",
        [
            "Đề nghị cho biết thủ tục bảo lưu và đồng thời cho em xin điểm trung bình hiện tại của em.",
            "Làm sao để chuyển ngành, và tiện thể cho em hỏi ngành nào đang hot nhất?",
            "Cho em hỏi đóng học phí thế nào với lại kỳ này em nợ bao nhiêu tiền vậy ạ?",
            "thủ tục hoãn thi và lịch thi lại của em",
            "Em muốn biết điều kiện học song ngành và cả ý kiến của thầy xem em có nên học không.",
            "Em định thôi học, thầy thấy em nên nghỉ hay cố học tiếp ạ?",
            "Cho em hỏi thủ tục xin nghỉ ốm và số điện thoại của trạm y tế trường.",
            "thu tuc chuyen truong va truong nao de chuyen nhat",
            "đk học lại + điểm môn đó của e là bn ạ",
            "Kính hỏi thủ tục xét tốt nghiệp sớm và dự kiến ngày trao bằng của khóa em ạ?",
        ],
    ),
]

# Đích tham chiếu theo ontology v0.4.1. Sau khi refactor ontology, chỉ cần sửa
# phần này; 390 câu hỏi ở trên là tài sản bền vững và giữ nguyên.
TEMPLATES = {
    "procedure-instruction": "SELECT ?answer WHERE {{ :{e} :instructionProvision ?part . ?part :officialText ?answer . }}",
    "procedure-eligibility": "SELECT ?answer WHERE {{ :{e} :eligibilityProvision ?part . ?part :officialText ?answer . }}",
    "procedure-deadline": "SELECT ?answer WHERE {{ :{e} :deadlineProvision ?part . ?part :officialText ?answer . }}",
    "procedure-submission-office": "SELECT ?answer WHERE {{ :{e} :submittedTo ?node . ?node rdfs:label ?answer . }}",
    "procedure-required-form": "SELECT ?answer WHERE {{ :{e} :requiresForm ?node . ?node rdfs:label ?answer . }}",
}

CELL_TARGETS = {
    "tuition-program-cohort-rate::InformationTechnology-K65": (
        "SELECT ?answer WHERE { ?rate :appliesToProgram :InformationTechnology ; "
        ":appliesToEducationLevel :UndergraduateLevel ; :amount ?answer . "
        "OPTIONAL { ?rate :minimumCohortNumber ?minimum . } "
        "FILTER (!BOUND(?minimum) || 65 >= ?minimum) } ORDER BY DESC(?minimum) LIMIT 1"
    ),
    "payment-method-list::TuitionPaymentProcedure": (
        "SELECT ?answer WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?method . "
        "?method rdfs:label ?answer . }"
    ),
    "academic-performance-band::score-7.50": (
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; "
        ":maximumValue ?maximum ; :resultLabel ?answer . "
        "FILTER (7.50 >= ?minimum && ?maximum >= 7.50) }"
    ),
    "graduation-classification-band::score-8.20": (
        "SELECT ?answer WHERE { ?band a :GraduationClassificationBand ; :minimumValue ?minimum ; "
        ":maximumValue ?maximum ; :resultLabel ?answer . "
        "FILTER (8.20 >= ?minimum && ?maximum >= 8.20) }"
    ),
    "form-list::FormCatalogue": (
        "SELECT ?answer WHERE { ?entry a :FormCatalogueEntry ; :listedTitle ?answer . }"
    ),
}

REJECTION_MARKER = "không có thông tin"


def expected_target(intent: str, entity: str) -> str:
    if intent == "no-information":
        return REJECTION_MARKER
    if intent in TEMPLATES:
        return TEMPLATES[intent].format(e=entity)
    return CELL_TARGETS[f"{intent}::{entity}"]


def build() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    index = 0
    for intent, entity, questions in CELLS:
        if len(questions) != len(PATTERNS):
            raise SystemExit(f"{intent}/{entity}: cần đúng {len(PATTERNS)} câu")
        for pattern, register, question in zip(PATTERNS, REGISTERS, questions, strict=True):
            index += 1
            rows.append(
                {
                    "id": f"probe-{index:04d}",
                    "cell": f"{intent}::{entity}",
                    "intent": intent,
                    "entity": entity,
                    "pattern": pattern,
                    "register": register,
                    "input": question,
                    "expected_target": expected_target(intent, entity),
                }
            )
    return rows


if __name__ == "__main__":
    rows = build()
    out = Path(__file__).with_name("paraphrase_probe.jsonl")
    out.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    print(f"{len(rows)} câu / {len(CELLS)} ô ngữ nghĩa -> {out}")
