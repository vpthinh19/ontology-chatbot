// Lược đồ và danh sách thực thể đang giữ trên trang, cùng các ô chọn có tìm kiếm (datalist).
import { api } from "./api.js";
import { element, encode } from "./ui.js";

export const state = { schema: [], properties: [], className: null, items: [], options: new Map(), entityId: null };

// --- danh sách chọn có tìm kiếm (mục của một loại, nguồn) --------------------------

export const classSpec = (name) => state.schema.find((item) => item.name === name);
// Nhớ LỜI HỨA chứ không nhớ kết quả: một form có nhiều dòng cùng trỏ tới một lớp, các dòng dựng
// song song nên nếu nhớ kết quả thì dòng nào cũng thấy "chưa có" và cùng hỏi máy chủ một danh sách.
export const optionsOf = (className) => {
  if (!state.options.has(className)) {
    state.options.set(className, api(`/entities?class=${encode(className)}`).then(({ items }) => items));
  }
  return state.options.get(className);
};
const optionText = (item) => `${item.label} (${item.id})`;
//: Thẻ datalist đã dựng cho từng lớp. Cũng nhớ lời hứa, không thì hai dòng dựng song song cùng thấy
//: "chưa có thẻ" và cùng thêm một thẻ, thành hai thẻ trùng định danh trong trang.
const datalists = new Map();
export const datalistFor = (className) => {
  const id = `dl-${className}`;
  if (!datalists.has(className)) {
    datalists.set(
      className,
      optionsOf(className).then((items) => {
        document.body.append(
          element("datalist", { id }, items.map((item) => element("option", { value: optionText(item) }))),
        );
        return id;
      }),
    );
  }
  return datalists.get(className);
};
// Quên danh sách của một lớp sau khi lớp đó đổi; không có tên thì quên hết (đổi lược đồ, đăng xuất).
export const clearOptions = (className) => {
  if (className === undefined) {
    state.options.clear();
    datalists.clear();
    document.querySelectorAll("datalist[id^='dl-']").forEach((node) => node.remove());
    return;
  }
  state.options.delete(className);
  datalists.delete(className);
  document.getElementById(`dl-${className}`)?.remove();
};
export const shown = async (className, id) => {
  if (!id) return "";
  const item = (await optionsOf(className)).find((entry) => entry.id === id);
  return item ? optionText(item) : id;
};
// Chữ trong ô chọn -> định danh; "" khi để trống; null khi không khớp mục nào.
export const resolve = async (className, text) => {
  const value = (text || "").trim();
  if (!value) return "";
  const items = await optionsOf(className);
  const inBrackets = value.match(/\(([A-Za-z0-9_]+)\)\s*$/);
  const byId = items.find((item) => item.id === (inBrackets ? inBrackets[1] : value));
  if (byId) return byId.id;
  const byLabel = items.filter((item) => item.label.toLocaleLowerCase("vi") === value.toLocaleLowerCase("vi"));
  return byLabel.length === 1 ? byLabel[0].id : null;
};
