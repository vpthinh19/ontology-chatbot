// Trang quản trị ontology. Form của mỗi loại thông tin sinh từ lược đồ mà máy chủ đọc
// trong shapes.ttl; máy chủ kiểm lại bằng SHACL trước khi ghi, nên trang này chỉ lo nhập.
const $ = (selector) => document.querySelector(selector);
const TOKEN_KEY = "ontchatbotAdminToken";
const state = { schema: [], className: null, items: [], options: new Map(), entityId: null };

let adminToken = (() => {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
})();

const api = async (path, { method = "GET", body } = {}) => {
  const response = await fetch(`/api/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || `Máy chủ trả lỗi ${response.status}.`);
    error.errors = data.errors || [];
    throw error;
  }
  return data;
};

// Dựng phần tử bằng DOM thay vì chuỗi HTML: nội dung ontology không bao giờ bị hiểu thành mã.
const element = (tag, props = {}, children = []) => {
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

const showStatus = (message, errors = []) => {
  const box = $("#status");
  box.replaceChildren(
    ...[
      element("p", { text: message }),
      errors.length ? element("ul", {}, errors.map((reason) => element("li", { text: reason }))) : null,
    ].filter(Boolean),
  );
  box.hidden = !message;
};

const run = async (task) => {
  try {
    await task();
  } catch (error) {
    showStatus(error.message, error.errors || []);
  }
};

const classSpec = (name) => state.schema.find((item) => item.name === name);
const blankStatement = (field) => ({ property: field?.property, value: "", source: null, coordinate: null });

const optionsOf = async (className) => {
  if (!state.options.has(className)) {
    const { items } = await api(`/entities?class=${encodeURIComponent(className)}`);
    state.options.set(className, items);
  }
  return state.options.get(className);
};

const renderClasses = () => {
  $("#classes").replaceChildren(
    ...state.schema.map((item) =>
      element(
        "button",
        {
          type: "button",
          class: item.name === state.className ? "active" : "",
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
      .filter((item) => item.label.toLocaleLowerCase("vi").includes(needle))
      .map((item) =>
        element(
          "li",
          {},
          element("button", {
            type: "button",
            class: item.id === state.entityId ? "active" : "",
            text: item.label,
            onclick: () => run(() => openEntity(item.id)),
          }),
        ),
      ),
  );
};

const loadSchema = async () => {
  state.schema = (await api("/schema")).classes;
  renderClasses();
};

const selectClass = async (name) => {
  state.className = name;
  state.entityId = null;
  renderClasses();
  $("#editor").hidden = true;
  state.items = (await api(`/entities?class=${encodeURIComponent(name)}`)).items;
  $("#list-title").textContent = classSpec(name).label;
  $("#list-panel").hidden = false;
  renderItems();
};

const openEntity = async (id) => {
  const entity = await api(`/entities/${encodeURIComponent(id)}`);
  state.entityId = id;
  renderItems();
  await renderEditor(entity);
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
    });
  });

const valueControl = async (field, value) => {
  const common = { class: "value", "aria-label": field.name };
  if (field.kind === "link" || field.kind === "choice") {
    const items = field.kind === "link" ? await optionsOf(field.target) : field.choices;
    return element("select", { ...common, value }, [
      element("option", { value: "", text: "— chọn —" }),
      ...items.map((item) => element("option", { value: item.id, text: item.label })),
    ]);
  }
  if (field.kind === "text") {
    return element("textarea", { ...common, rows: String(value).length > 160 ? 6 : 2, value });
  }
  const type = { integer: "number", decimal: "number", date: "date", uri: "url" }[field.kind] || "text";
  return element("input", { ...common, type, step: field.kind === "decimal" ? "any" : undefined, value });
};

const sourceControl = async (field, statement) => {
  if (field.sourced === null) return element("span", { class: "no-source", text: "Ô này không gắn nguồn" });
  const sources = await optionsOf("Nguon");
  return element("div", { class: "source" }, [
    element("select", { class: "source-id", "aria-label": "Nguồn", value: statement.source || "" }, [
      element("option", { value: "", text: field.sourced ? "— chọn nguồn —" : "— không gắn nguồn —" }),
      ...sources.map((source) => element("option", { value: source.id, text: `${source.label} (${source.id})` })),
    ]),
    element("input", {
      class: "coordinate",
      "aria-label": "Vị trí trong nguồn",
      placeholder: "Vị trí, ví dụ khoản 1 Điều 24",
      value: statement.coordinate || "",
    }),
  ]);
};

const statementRow = async (spec, statement) => {
  const row = element("div", { class: "statement" });
  const render = async (current) => {
    const field = spec.fields.find((item) => item.property === current.property) || spec.fields[0];
    const picker = element(
      "select",
      {
        class: "property",
        "aria-label": "Ô",
        value: field.property,
        onchange: (event) =>
          run(() => render(blankStatement(spec.fields.find((item) => item.property === event.target.value)))),
      },
      spec.fields.map((item) => element("option", { value: item.property, text: item.required ? `${item.name} *` : item.name })),
    );
    row.replaceChildren(
      picker,
      await valueControl(field, current.value ?? ""),
      await sourceControl(field, current),
      element("button", {
        type: "button",
        class: "remove",
        title: "Bỏ dòng này",
        "aria-label": "Bỏ dòng này",
        text: "✕",
        onclick: () => row.remove(),
      }),
    );
  };
  await render(statement);
  return row;
};

const collect = (spec, rows, labelInput, altInput) => ({
  class: spec.name,
  label: labelInput.value,
  altLabels: altInput ? altInput.value.split("\n").map((name) => name.trim()).filter(Boolean) : [],
  statements: [...rows.querySelectorAll(".statement")]
    .map((row) => ({
      property: row.querySelector(".property").value,
      value: row.querySelector(".value").value,
      source: row.querySelector(".source-id")?.value || null,
      coordinate: row.querySelector(".coordinate")?.value.trim() || null,
    }))
    .filter((statement) => statement.value.trim()),
});

const renderEditor = async (entity) => {
  const spec = classSpec(entity.class);
  const rows = element("div", { class: "statements" }, await Promise.all(entity.statements.map((item) => statementRow(spec, item))));
  const labelInput = element("input", { id: "entity-label", required: true, value: entity.label });
  const altInput = spec.altLabels
    ? element("textarea", { id: "entity-alt", rows: 2, value: entity.altLabels.join("\n") })
    : null;

  const save = (event) => {
    event.preventDefault();
    run(async () => {
      showStatus("Đang kiểm tra theo lược đồ và lưu…");
      const payload = collect(spec, rows, labelInput, altInput);
      const { id } = entity.id
        ? await api(`/entities/${encodeURIComponent(entity.id)}`, { method: "PUT", body: payload })
        : await api("/entities", { method: "POST", body: payload });
      state.options.clear();
      await loadSchema();
      await selectClass(spec.name);
      await openEntity(id);
      showStatus("Đã lưu. Trợ lý dùng dữ liệu mới từ lượt hỏi kế tiếp.");
    });
  };
  const remove = () =>
    run(async () => {
      if (!window.confirm(`Xoá «${entity.label}»? Việc này không hoàn tác được.`)) return;
      await api(`/entities/${encodeURIComponent(entity.id)}`, { method: "DELETE" });
      state.options.clear();
      await loadSchema();
      await selectClass(spec.name);
      showStatus("Đã xoá.");
    });
  const addRow = () => run(async () => rows.append(await statementRow(spec, blankStatement(spec.fields[0]))));

  $("#editor").replaceChildren(
    element("form", { class: "entity-form", onsubmit: save }, [
      element("h2", { text: entity.id ? entity.label : `Thêm mục mới: ${spec.label}` }),
      element("p", { class: "muted", text: entity.id ? `Định danh: ${entity.id}` : "Định danh được sinh từ tên khi lưu." }),
      element("label", { for: "entity-label", text: "Tên" }),
      labelInput,
      altInput && element("label", { for: "entity-alt", text: "Tên gọi khác, mỗi dòng một tên" }),
      altInput,
      element("h3", { text: "Các câu" }),
      element("p", {
        class: "muted",
        text: "Ô có dấu * là bắt buộc. Câu mang nội dung phải chọn nguồn và ghi vị trí trong nguồn.",
      }),
      rows,
      spec.fields.length ? element("button", { type: "button", class: "add-row", text: "Thêm dòng", onclick: addRow }) : null,
      element("div", { class: "actions" }, [
        element("button", { type: "submit", class: "primary", text: "Lưu" }),
        entity.id ? element("button", { type: "button", class: "danger", text: "Xoá mục", onclick: remove }) : null,
      ]),
      entity.references.length
        ? element("section", { class: "references" }, [
            element("h3", { text: "Đang được trỏ tới từ" }),
            element("ul", {}, entity.references.map((item) => element("li", { text: `${item.label} · ${item.property}` }))),
          ])
        : null,
    ]),
  );
  $("#editor").hidden = false;
};

const start = () =>
  run(async () => {
    if (!adminToken) {
      showStatus("Nhập khoá quản trị để bắt đầu.");
      return;
    }
    await loadSchema();
    showStatus("");
  });

$("#token").value = adminToken;
$("#token-form").addEventListener("submit", (event) => {
  event.preventDefault();
  adminToken = $("#token").value.trim();
  try {
    sessionStorage.setItem(TOKEN_KEY, adminToken);
  } catch {
    // Trình duyệt chặn lưu thì khoá chỉ sống tới khi tải lại trang.
  }
  start();
});
$("#filter").addEventListener("input", renderItems);
$("#new-btn").addEventListener("click", newEntity);
try {
  document.body.classList.toggle("light-theme", localStorage.getItem("themeColor") === "light_mode");
} catch {
  // Không đọc được lựa chọn giao diện thì dùng nền tối mặc định.
}
start();
