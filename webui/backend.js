// Gọi backend qua proxy của Vercel. Trang không chờ máy chủ khởi động: mở trang là gửi một lượt
// đánh thức rồi quên, còn câu hỏi đầu tiên cứ gửi thẳng - Cloud Run giữ request trong lúc máy lên,
// nên người dùng chỉ thấy câu trả lời tới chậm hơn một chút chứ không phải chờ chấm trạng thái.

export const apiUrl = (path) => `/api${path}`;
// Khoá dịch vụ sai: hỏi lại bao nhiêu lần cũng vẫn sai.
export const isRejectedKey = (status) => status === 401 || status === 403;
export const REJECTED_KEY_TEXT = "Máy chủ từ chối xác thực dịch vụ của trang này.";

export const warmUp = () => {
  // Không chờ kết quả và nuốt mọi lỗi: đây chỉ là cú hích cho Cloud Run cấp máy.
  fetch(apiUrl("/healthz"), { cache: "no-store" }).catch(() => {});
};
