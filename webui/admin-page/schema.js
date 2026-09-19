// Lược đồ và danh sách thực thể đang giữ trên trang, cùng các ô chọn có tìm kiếm (datalist).
import { api } from "./api.js";
import { element, encode } from "./ui.js";

export const state = { schema: [], properties: [], className: null, items: [], options: new Map(), entityId: null };

// --- danh sách chọn có tìm kiếm (mục của một loại, nguồn) --------------------------

export const classSpec = (name) => state.schema.find((item) => item.name === name);
export const optionsOf = async (className) => {
  if (!state.options.has(className)) {
    const { items } = await api(`/entities?class=${encode(className)}`);
    state.options.set(className, items);
  }
  return state.options.get(className);
};
const optionText = (item) => `${item.label} (${item.id})`;
export const datalistFor = async (className) => {
  const id = `dl-${className}`;
  if (!document.getElementById(id)) {
    const items = await optionsOf(className);
    document.body.append(element("datalist", { id }, items.map((item) => element("option", { value: optionText(item) }))));
  }
  return id;
};
export const clearOptions = () => {
  state.options.clear();
  document.querySelectorAll("datalist[id^='dl-']").forEach((node) => node.remove());
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
