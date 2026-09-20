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

// Mô hình thỉnh thoảng đặt tên liên kết là "Link" thay vì gọi đúng tên nguồn. Người đọc là sinh viên,
// nên chữ hiện lên phải là "Nguồn"; tên nguồn thật thì giữ nguyên.
const VAGUE_LINK_TEXT = new Set(["link", "links", "liên kết", "url", "xem", "tại đây", "đây"]);

const purifier = DOMPurify;
purifier.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
    if (VAGUE_LINK_TEXT.has(node.textContent.trim().toLowerCase())) node.textContent = "Nguồn";
  }
});

export const renderMarkdown = (text) =>
  purifier.sanitize(markdown.parse(plainMath(String(text ?? ""))), {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ["href", "title", "start"],
  });
