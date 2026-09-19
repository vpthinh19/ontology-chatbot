// Trang quản trị ontology. Form của mỗi lớp sinh từ lược đồ (shapes.ttl) mà máy chủ gửi; máy chủ kiểm lại
// bằng SHACL trước khi ghi, nên trang lo nhập liệu, chỉ chỗ sai và sửa chính lược đồ.
//
//   admin-page/ui.js             phần tử DOM, thông báo, tô đỏ chỗ sai
//   admin-page/api.js            gọi /api/admin
//   admin-page/schema.js         lược đồ đang giữ, ô chọn có tìm kiếm
//   admin-page/entity-editor.js  form thực thể
//   admin-page/class-editor.js   form lớp và thuộc tính
//   admin-page/chats.js          lịch sử chat
import { mountAccount } from "./account.js";
import { api, onUnauthorized } from "./admin-page/api.js";
import { loadChats } from "./admin-page/chats.js";
import { renderClassEditor } from "./admin-page/class-editor.js";
import { blankStatement, renderEditor } from "./admin-page/entity-editor.js";
import { classSpec, state } from "./admin-page/schema.js";
import { $, element, encode, run, showStatus } from "./admin-page/ui.js";
import { applySavedTheme } from "./theme.js";

const renderClasses = () => {
  $("#classes").replaceChildren(
    ...state.schema.map((item) =>
      element(
        "button",
        {
          type: "button",
          class: item.name === state.className ? "active" : "",
          title: `${item.label} (${item.name})`,
          onclick: () => run(() => selectClass(item.name)),
        },
        [element("span", { text: item.label }), element("span", { class: "count", text: String(item.count) })],
      ),
    ),
  );
};

const renderItems = () => {
  const needle = $("#filter").value.trim().toLocaleLowerCase("vi");
  $("#items").replaceChildren(
    ...state.items
      .filter((item) => `${item.label} ${item.id}`.toLocaleLowerCase("vi").includes(needle))
      .map((item) =>
        element(
          "li",
          {},
          element("button", {
            type: "button",
            class: item.id === state.entityId ? "active" : "",
            text: item.label,
            title: item.id,
            onclick: () => run(() => openEntity(item.id)),
          }),
        ),
      ),
  );
};

const loadSchema = async () => {
  const data = await api("/schema");
  state.schema = data.classes;
  state.properties = data.properties;
  renderClasses();
};

const selectClass = async (name, { keepEditor = false } = {}) => {
  state.className = name;
  state.entityId = null;
  renderClasses();
  if (!keepEditor) $("#editor").hidden = true;
  state.items = (await api(`/entities?class=${encode(name)}`)).items;
  $("#list-title").textContent = classSpec(name).label;
  $("#list-panel").hidden = false;
  renderItems();
};

const openEntity = async (id) => {
  const entity = await api(`/entities/${encode(id)}`);
  state.entityId = id;
  renderItems();
  await renderEditor(entity, entityNav);
};

const newEntity = () =>
  run(async () => {
    const spec = classSpec(state.className);
    state.entityId = null;
    renderItems();
    await renderEditor({
      id: null,
      class: spec.name,
      label: "",
      altLabels: [],
      references: [],
      statements: spec.fields.filter((field) => field.required).map(blankStatement),
    }, entityNav);
  });


// Sau khi lưu hay xoá ở form: nạp lại lược đồ, danh sách, và mở lại đúng chỗ.
const entityNav = {
  saved: async (className, id) => {
    await loadSchema();
    await selectClass(className, { keepEditor: true });
    await openEntity(id);
  },
  deleted: async (className) => {
    await loadSchema();
    await selectClass(className);
  },
};

const classNav = {
  saved: async (name) => {
    await loadSchema();
    await selectClass(name, { keepEditor: true });
    renderClassEditor(classSpec(name), classNav);
  },
  deleted: async () => {
    await loadSchema();
    state.className = null;
    renderClasses();
    $("#list-panel").hidden = true;
    $("#editor").hidden = true;
  },
};

// --- đăng nhập và chuyển khu vực ------------------------------------------------------

const showView = (view) => {
  $("#data-view").hidden = view !== "data";
  $("#chat-view").hidden = view !== "chat";
  document.querySelectorAll("#tabs button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  if (view === "chat") run(loadChats);
};

const showLogin = () => {
  $("#tabs").hidden = true;
  $("#data-view").hidden = true;
  $("#chat-view").hidden = true;
  showStatus("Đăng nhập tài khoản quản trị để xem và sửa dữ liệu.");
};

const enter = async () => {
  $("#tabs").hidden = false;
  await loadSchema();
  showView("data");
  showStatus("");
};

document.querySelectorAll("#tabs button").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
$("#chat-filters").addEventListener("submit", (event) => {
  event.preventDefault();
  run(loadChats);
});
$("#filter").addEventListener("input", renderItems);
$("#new-btn").addEventListener("click", newEntity);
$("#edit-class-btn").addEventListener("click", () => run(async () => renderClassEditor(classSpec(state.className), classNav)));
$("#new-class-btn").addEventListener("click", () => run(async () => renderClassEditor(null, classNav)));
applySavedTheme();
const account = mountAccount($("#account"), {
  other: { href: "/", label: "Hỏi đáp" },
  openWhenGuest: true,
  onChange: (role) => (role === "admin" ? run(enter) : showLogin()),
});
onUnauthorized(() => account.signedOut());
