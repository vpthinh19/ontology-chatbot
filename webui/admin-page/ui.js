// Công cụ dựng giao diện của trang quản trị: phần tử DOM, thông báo nổi, ô chữ tự cao, tô đỏ chỗ sai.

export const $ = (selector) => document.querySelector(selector);

// Dựng phần tử bằng DOM thay vì chuỗi HTML: nội dung ontology không bao giờ bị hiểu thành mã.
export const element = (tag, props = {}, children = []) => {
  const node = document.createElement(tag);
  let value;
  for (const [key, prop] of Object.entries(props)) {
    if (prop === undefined || prop === null || prop === false) continue;
    if (key === "value") value = prop;
    else if (key === "class") node.className = prop;
    else if (key === "text") node.textContent = prop;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), prop);
    else node.setAttribute(key, prop === true ? "" : String(prop));
  }
  node.append(...[].concat(children).filter(Boolean));
  if (value !== undefined) node.value = value;
  return node;
};
export const option = (value, text) => element("option", { value, text });
export const encode = encodeURIComponent;
export const lines = (text) => text.split("\n").map((line) => line.trim()).filter(Boolean);

// --- thông báo nổi ---------------------------------------------------------------

let statusTimer = null;
export const showStatus = (message, errors = [], tone = "info") => {
  const box = $("#status");
  clearTimeout(statusTimer);
  if (!message) {
    box.hidden = true;
    return;
  }
  box.className = `status-${tone}`;
  box.replaceChildren(
    ...[
      element("button", {
        type: "button",
        class: "close",
        "aria-label": "Đóng thông báo",
        text: "✕",
        onclick: () => {
          box.hidden = true;
        },
      }),
      element("p", { text: message }),
      errors.length ? element("ul", {}, errors.map((reason) => element("li", { text: reason }))) : null,
    ].filter(Boolean),
  );
  box.hidden = false;
  if (tone === "ok") statusTimer = setTimeout(() => (box.hidden = true), 4000);
};

export const run = async (task) => {
  try {
    await task();
  } catch (error) {
    showStatus(error.message, error.errors || [], "error");
  }
};

// --- ô chữ cao theo nội dung -----------------------------------------------------

export const autosize = (area) => {
  if (!area.isConnected) return;
  area.style.height = "auto";
  area.style.height = `${area.scrollHeight + 2}px`;
};
export const growing = (props) =>
  element("textarea", { ...props, class: `${props.class || ""} autosize`.trim(), rows: 1, oninput: (e) => autosize(e.target) });
export const fitAll = (root) => requestAnimationFrame(() => root.querySelectorAll("textarea.autosize").forEach(autosize));

// Định danh sinh từ tên, cùng luật với máy chủ: bỏ dấu, viết hoa chữ đầu mỗi từ, nối liền.
export const iriName = (label) =>
  (label.replace(/đ/g, "d").replace(/Đ/g, "D").normalize("NFD").replace(/[\u0300-\u036f]/g, "").match(/[A-Za-z0-9]+/g) || [])
    .map((word) => (/^\d+$/.test(word) ? word : word[0].toUpperCase() + word.slice(1).toLowerCase()))
    .join("");
export const propertyName = (label) => {
  const name = iriName(label);
  return name ? name[0].toLowerCase() + name.slice(1) : "";
};

// --- tô đỏ chỗ sai ---------------------------------------------------------------

export const clearMarks = (root) => {
  root.querySelectorAll(".invalid").forEach((node) => node.classList.remove("invalid"));
  root.querySelectorAll(".field-error").forEach((node) => node.remove());
};
export const mark = (node, message) => {
  if (!node) return false;
  node.classList.add("invalid");
  const note = element("p", { class: "field-error", text: message });
  if (node.classList.contains("statement") || node.classList.contains("field-card")) node.append(note);
  else node.after(note);
  return true;
};
// Cột sửa tự cuộn: mở mục hay loại khác thì về đầu cột.
export const showEditor = (form) => {
  const editor = $("#editor");
  editor.replaceChildren(form);
  editor.hidden = false;
  editor.scrollTop = 0;
};
export const focusFirstMark = (root) => root.querySelector(".invalid")?.scrollIntoView({ behavior: "smooth", block: "center" });

export const checkbox = (text, checked, key) => {
  const input = element("input", { type: "checkbox", "data-key": key });
  input.checked = Boolean(checked);
  return { input, label: element("label", { class: "check" }, [input, element("span", { text })]) };
};
