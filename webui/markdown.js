// Hiển thị câu trả lời markdown của mô hình, dùng chung cho trang hỏi đáp và trang quản trị. Thư viện
// chuẩn (marked, theo CommonMark + GFM) đọc markdown; DOMPurify lọc mọi thứ có thể chạy được, vì
// chữ đến từ mô hình ngôn ngữ; liên kết mở ở tab mới.
import DOMPurify from "dompurify";
import { Marked } from "marked";

// Mô hình được dặn không viết công thức, nhưng đôi khi vẫn viết kiểu $\ge 140$. Đổi các lệnh hay
// gặp thành ký tự và bỏ dấu $, để người đọc không thấy mã thô.
const SYMBOLS = {
  ge: "≥", geq: "≥", le: "≤", leq: "≤", ne: "≠", neq: "≠", approx: "≈", pm: "±",
  times: "×", div: "÷", cdot: "·", rightarrow: "→", to: "→", leftarrow: "←", Rightarrow: "⇒",
  Sigma: "Σ", sum: "Σ", infty: "∞",
};
const plainMath = (text) =>
  text.replace(/\$([^$\n]*\\[A-Za-z]+[^$\n]*)\$/g, (_, body) =>
    body.replace(/\\([A-Za-z]+)/g, (match, name) => SYMBOLS[name] ?? match).replace(/\\%/g, "%").trim(),
  );

const ALLOWED_TAGS = [
  "p", "br", "strong", "em", "del", "a", "ul", "ol", "li", "blockquote", "code", "pre", "hr",
  "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td",
];

const markdown = new Marked({ gfm: true, breaks: true });
// Chữ thô của mô hình không được thành thẻ HTML: marked giữ nguyên HTML trong markdown, nên hiện nó
// thành chữ thay vì để DOMPurify phải đoán.
markdown.use({ renderer: { html: ({ text }) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") } });

// Mô hình hay đặt tên liên kết bằng chữ dẫn dắt rỗng nghĩa: đếm trên 140 câu trả lời đã ghi lại thì
// gặp "Link", "link", "chi tiết", "Xem chi tiết", "Xem tại đây", "Chi tiết tại đây", "Link tải 1".
// Người đọc là sinh viên, "Xem chi tiết" dễ tưởng là trang khác của hệ thống chứ không phải văn bản
// gốc, nên chữ hiện lên phải là "Nguồn". Tên gọi đúng nguồn, như "khoản 1 Điều 11 Quy chế", giữ nguyên.
const FILLER_WORDS = new Set([
  "link", "links", "url", "liên", "kết", "xem", "chi", "tiết", "tại", "đây", "ở", "vào",
  "nhấn", "bấm", "truy", "cập", "tải", "về", "nguồn", "here", "click",
]);
// Rỗng nghĩa khi MỌI chữ đều là từ dẫn dắt (số thứ tự không tính), nên "Link tải 2" cũng là rỗng
// nghĩa còn "Trang Cơ sở vật chất" thì không.
const vagueLinkText = (text) => {
  const words = text.toLowerCase().split(/[\s.,:;!?()[\]{}"'`/\\-]+/).filter(Boolean);
  return words.length > 0 && words.every((word) => FILLER_WORDS.has(word) || /^\d+$/.test(word));
};

const purifier = DOMPurify;
purifier.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
    if (vagueLinkText(node.textContent.trim())) node.textContent = "Nguồn";
  }
});

export const renderMarkdown = (text) =>
  purifier.sanitize(markdown.parse(plainMath(String(text ?? ""))), {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ["href", "title", "start"],
  });
