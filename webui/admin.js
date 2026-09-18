// Trang quản trị ontology. Form của mỗi loại thông tin sinh từ lược đồ mà máy chủ đọc
// trong shapes.ttl; máy chủ kiểm lại bằng SHACL trước khi ghi, nên trang này lo nhập,
// chỉ chỗ sai, và sửa chính lược đồ (loại, thuộc tính).
const $ = (selector) => document.querySelector(selector);
const TOKEN_KEY = "ontchatbotAdminToken";
const KIND_NAMES = {
  text: "Chữ (tiếng Việt)",
  string: "Chuỗi ký tự (mã, số hiệu, email…)",
  integer: "Số nguyên",
  decimal: "Số thập phân",
  date: "Ngày",
  uri: "Địa chỉ web",
  link: "Trỏ tới một mục (thuộc tính đối tượng)",
  choice: "Chọn trong danh sách",
};
const SOURCE_RULES = [
  ["true", "Bắt buộc có nguồn"],
  ["false", "Có thể có nguồn"],
  ["null", "Không gắn nguồn"],
];
const state = { schema: [], properties: [], className: null, items: [], options: new Map(), entityId: null };

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
    Object.assign(error, {
      status: response.status,
      errors: data.errors || [],
      details: data.details || [],
      confirm: Boolean(data.confirm),
    });
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
const option = (value, text) => element("option", { value, text });
const encode = encodeURIComponent;
const lines = (text) => text.split("\n").map((line) => line.trim()).filter(Boolean);

// --- thông báo nổi ---------------------------------------------------------------

let statusTimer = null;
const showStatus = (message, errors = [], tone = "info") => {
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

const run = async (task) => {
  try {
    await task();
  } catch (error) {
    showStatus(error.message, error.errors || [], "error");
  }
};

// --- ô chữ cao theo nội dung -----------------------------------------------------

const autosize = (area) => {
  if (!area.isConnected) return;
  area.style.height = "auto";
  area.style.height = `${area.scrollHeight + 2}px`;
};
const growing = (props) =>
  element("textarea", { ...props, class: `${props.class || ""} autosize`.trim(), rows: 1, oninput: (e) => autosize(e.target) });
const fitAll = (root) => requestAnimationFrame(() => root.querySelectorAll("textarea.autosize").forEach(autosize));

// Định danh sinh từ tên, cùng luật với máy chủ: bỏ dấu, viết hoa chữ đầu mỗi từ, nối liền.
const iriName = (label) =>
  (label.replace(/đ/g, "d").replace(/Đ/g, "D").normalize("NFD").replace(/[\u0300-\u036f]/g, "").match(/[A-Za-z0-9]+/g) || [])
    .map((word) => (/^\d+$/.test(word) ? word : word[0].toUpperCase() + word.slice(1).toLowerCase()))
    .join("");
const propertyName = (label) => {
  const name = iriName(label);
  return name ? name[0].toLowerCase() + name.slice(1) : "";
};

// --- danh sách chọn có tìm kiếm (mục của một loại, nguồn) --------------------------

const classSpec = (name) => state.schema.find((item) => item.name === name);
const optionsOf = async (className) => {
  if (!state.options.has(className)) {
    const { items } = await api(`/entities?class=${encode(className)}`);
    state.options.set(className, items);
  }
  return state.options.get(className);
};
const optionText = (item) => `${item.label} (${item.id})`;
const datalistFor = async (className) => {
  const id = `dl-${className}`;
  if (!document.getElementById(id)) {
    const items = await optionsOf(className);
    document.body.append(element("datalist", { id }, items.map((item) => element("option", { value: optionText(item) }))));
  }
  return id;
};
const clearOptions = () => {
  state.options.clear();
  document.querySelectorAll("datalist[id^='dl-']").forEach((node) => node.remove());
};
const shown = async (className, id) => {
  if (!id) return "";
  const item = (await optionsOf(className)).find((entry) => entry.id === id);
  return item ? optionText(item) : id;
};
// Chữ trong ô chọn -> định danh; "" khi để trống; null khi không khớp mục nào.
const resolve = async (className, text) => {
  const value = (text || "").trim();
  if (!value) return "";
  const items = await optionsOf(className);
  const inBrackets = value.match(/\(([A-Za-z0-9_]+)\)\s*$/);
  const byId = items.find((item) => item.id === (inBrackets ? inBrackets[1] : value));
  if (byId) return byId.id;
  const byLabel = items.filter((item) => item.label.toLocaleLowerCase("vi") === value.toLocaleLowerCase("vi"));
  return byLabel.length === 1 ? byLabel[0].id : null;
};

// --- tô đỏ chỗ sai ---------------------------------------------------------------

const clearMarks = (root) => {
  root.querySelectorAll(".invalid").forEach((node) => node.classList.remove("invalid"));
  root.querySelectorAll(".field-error").forEach((node) => node.remove());
};
const mark = (node, message) => {
  if (!node) return false;
  node.classList.add("invalid");
  const note = element("p", { class: "field-error", text: message });
  if (node.classList.contains("statement") || node.classList.contains("field-card")) node.append(note);
  else node.after(note);
  return true;
};
// Cột sửa tự cuộn: mở mục hay loại khác thì về đầu cột.
const showEditor = (form) => {
  const editor = $("#editor");
  editor.replaceChildren(form);
  editor.hidden = false;
  editor.scrollTop = 0;
};
const focusFirstMark = (root) => root.querySelector(".invalid")?.scrollIntoView({ behavior: "smooth", block: "center" });

// --- cột loại và cột mục -----------------------------------------------------------

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

// --- sửa một mục -------------------------------------------------------------------

const blankStatement = (field) => ({ property: field?.property, value: "", source: null, coordinate: null });
const sameValueKind = (a, b) => a && b && a.kind === b.kind && (a.kind !== "link" || a.target === b.target);

const valueControl = async (field, value) => {
  const common = { class: "value", "aria-label": field ? field.name : "giá trị" };
  if (!field) return element("input", { ...common, type: "text", value });
  if (field.kind === "link") {
    const target = classSpec(field.target);
    return element("input", {
      ...common,
      list: await datalistFor(field.target),
      placeholder: `Gõ để tìm trong «${target ? target.label : field.target}»`,
      value: await shown(field.target, value),
    });
  }
  if (field.kind === "choice") {
    return element("select", { ...common, value }, [
      option("", "Chọn…"),
      ...field.choices.map((choice) => option(choice.id, choice.label)),
    ]);
  }
  if (field.kind === "text") return growing({ ...common, value });
  const type = { integer: "number", decimal: "number", date: "date", uri: "url" }[field.kind] || "text";
  return element("input", { ...common, type, step: field.kind === "decimal" ? "any" : undefined, value });
};

const sourceControl = async (field, statement) => {
  if (field && field.sourced === null) return element("span", { class: "no-source", text: "Ô này không gắn nguồn" });
  const source = element("input", {
    class: "source-id",
    list: await datalistFor("Nguon"),
    "aria-label": "Nguồn",
    placeholder: field && field.sourced ? "Nguồn (bắt buộc), gõ để tìm" : "Nguồn (nếu có), gõ để tìm",
    value: await shown("Nguon", statement.source),
    oninput: (event) => (event.target.title = event.target.value),
  });
  source.title = source.value;
  return element("div", { class: "source" }, [
    source,
    element("input", {
      class: "coordinate",
      "aria-label": "Vị trí trong nguồn",
      placeholder: "Vị trí, ví dụ khoản 1 Điều 24",
      value: statement.coordinate || "",
    }),
  ]);
};

// Dòng như đang hiện trên form (chữ trong ô chọn chưa đổi thành định danh).
const readRow = (row) => ({
  property: row.querySelector(".property").value,
  value: row.querySelector(".value")?.value ?? "",
  source: row.querySelector(".source-id")?.value ?? "",
  coordinate: row.querySelector(".coordinate")?.value ?? "",
});

const statementRow = async (spec, statement) => {
  const row = element("div", { class: "statement" });
  const render = async (current) => {
    const field = spec.fields.find((item) => item.property === current.property) || null;
    row.field = field;
    const choices = spec.fields.map((item) => option(item.property, item.required ? `${item.name} *` : item.name));
    if (!field) choices.unshift(option(current.property, `${current.property} (không thuộc loại này)`));
    const picker = element(
      "select",
      {
        class: "property",
        "aria-label": "Ô",
        value: current.property,
        onchange: (event) =>
          run(async () => {
            const next = spec.fields.find((item) => item.property === event.target.value);
            const before = readRow(row);
            // Đổi ô mà vẫn giữ những gì đã gõ còn dùng được: giá trị khi cùng kiểu, nguồn và vị trí khi ô mới gắn nguồn.
            const keepValue =
              sameValueKind(row.field, next) && (next.kind !== "choice" || next.choices.some((c) => c.id === before.value));
            let value = keepValue ? before.value : "";
            if (keepValue && next.kind === "link") value = (await resolve(next.target, before.value)) ?? before.value;
            const keepSource = next.sourced !== null;
            await render({
              property: next.property,
              value,
              source: keepSource ? ((await resolve("Nguon", before.source)) ?? before.source) : null,
              coordinate: keepSource ? before.coordinate : null,
            });
          }),
      },
      choices,
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
    fitAll(row);
  };
  await render(statement);
  return row;
};

// Các câu gửi lên, kèm vị trí dòng trên form để lỗi chỉ đúng dòng. Dòng trống hẳn bị bỏ qua.
const collectStatements = async (rows) => {
  const statements = [];
  const problems = [];
  for (const [row, node] of [...rows.querySelectorAll(".statement")].entries()) {
    const field = node.field;
    const shown = readRow(node);
    const coordinate = shown.coordinate.trim();
    if (!shown.value.trim() && !shown.source.trim() && !coordinate) continue;
    let value = shown.value;
    if (field && field.kind === "link" && value.trim()) {
      value = await resolve(field.target, value);
      if (value === null) {
        const target = classSpec(field.target);
        problems.push({
          row,
          message: `Dòng ${row + 1} (${field.name}): không có mục «${shown.value.trim()}» trong loại «${target ? target.label : field.target}»; hãy chọn trong danh sách gợi ý.`,
        });
        continue;
      }
    }
    const source = await resolve("Nguon", shown.source);
    if (source === null) {
      problems.push({ row, message: `Dòng ${row + 1}: không có nguồn «${shown.source.trim()}»; hãy chọn trong danh sách gợi ý.` });
      continue;
    }
    statements.push({ row, property: shown.property, value, source: source || null, coordinate: coordinate || null });
  }
  return { statements, problems };
};

const renderEditor = async (entity) => {
  const spec = classSpec(entity.class);
  const isNew = !entity.id;
  const rows = element("div", { class: "statements" }, await Promise.all(entity.statements.map((item) => statementRow(spec, item))));
  const addRow = async (statement) => {
    const row = await statementRow(spec, statement);
    rows.append(row);
    return row;
  };
  const idInput = element("input", {
    id: "entity-id",
    "data-where": "id",
    spellcheck: "false",
    value: entity.id || "",
    placeholder: isNew ? iriName(entity.label) || "sinh từ tên khi lưu" : "",
  });
  const labelInput = element("input", {
    id: "entity-label",
    "data-where": "label",
    value: entity.label,
    oninput: () => {
      if (isNew) idInput.placeholder = iriName(labelInput.value) || "sinh từ tên khi lưu";
    },
  });
  const classSelect = element(
    "select",
    {
      id: "entity-class",
      "data-where": "class",
      value: entity.class,
      onchange: () =>
        run(async () => {
          // Đổi loại: dựng lại form theo loại mới, giữ nguyên những gì đang gõ.
          await renderEditor({
            ...entity,
            class: classSelect.value,
            label: labelInput.value,
            altLabels: altInput ? lines(altInput.value) : [],
            statements: [...rows.querySelectorAll(".statement")].map(readRow),
          });
          if (!isNew) $("#entity-id").value = idInput.value;
        }),
    },
    state.schema.map((item) => option(item.name, item.label)),
  );
  const altInput = spec.altLabels
    ? growing({ id: "entity-alt", "data-where": "altLabels", value: entity.altLabels.join("\n") })
    : null;

  let form;
  const showProblems = async (details) => {
    clearMarks(form);
    const rowNodes = [...rows.querySelectorAll(".statement")];
    for (const detail of details) {
      if (Number.isInteger(detail.row)) mark(rowNodes[detail.row], detail.message);
      else if (detail.where) mark(form.querySelector(`[data-where="${detail.where}"]`), detail.message);
      else if (detail.property === "label") mark(labelInput, detail.message);
      else if (detail.property && (!detail.entity || detail.entity === (entity.id || idInput.value || idInput.placeholder))) {
        const matching = rowNodes.filter((node) => node.querySelector(".property").value === detail.property);
        if (matching.length) matching.forEach((node) => mark(node, detail.message));
        else if (spec.fields.some((field) => field.property === detail.property)) {
          mark(await addRow(blankStatement({ property: detail.property })), detail.message);
        }
      }
    }
    focusFirstMark(form);
  };

  const save = (event) => {
    event.preventDefault();
    run(async () => {
      const { statements, problems } = await collectStatements(rows);
      if (problems.length) {
        await showProblems(problems);
        showStatus("Còn chỗ chưa hợp lệ, đã tô đỏ trên form.", problems.map((p) => p.message), "error");
        return;
      }
      clearMarks(form);
      showStatus("Đang kiểm tra theo lược đồ và lưu…");
      const payload = {
        class: classSelect.value,
        label: labelInput.value,
        altLabels: altInput ? lines(altInput.value) : [],
        statements,
        version: entity.version,
      };
      if (idInput.value.trim()) payload.id = idInput.value.trim();
      try {
        const { id } = isNew
          ? await api("/entities", { method: "POST", body: payload })
          : await api(`/entities/${encode(entity.id)}`, { method: "PUT", body: payload });
        clearOptions();
        await loadSchema();
        await selectClass(payload.class, { keepEditor: true });
        await openEntity(id);
        showStatus("Đã lưu. Trợ lý dùng dữ liệu mới từ lượt hỏi kế tiếp.", [], "ok");
      } catch (error) {
        await showProblems(error.details || []);
        throw error;
      }
    });
  };
  const remove = () =>
    run(async () => {
      if (!window.confirm(`Xoá «${entity.label}»? Việc này không hoàn tác được.`)) return;
      await api(`/entities/${encode(entity.id)}?version=${encode(entity.version || "")}`, { method: "DELETE" });
      clearOptions();
      await loadSchema();
      await selectClass(spec.name);
      showStatus("Đã xoá.", [], "ok");
    });

  form = element("form", { class: "entity-form", onsubmit: save, novalidate: true }, [
    element("h2", { text: isNew ? `Thêm mục mới: ${spec.label}` : entity.label }),
    element("div", { class: "two" }, [
      element("label", {}, [element("span", { text: "Tên" }), labelInput]),
      element("label", {}, [element("span", { text: "Loại" }), classSelect]),
    ]),
    element("label", { for: "entity-id", text: "Định danh (IRI)" }),
    idInput,
    element("p", {
      class: "muted",
      text: isNew
        ? "Để trống thì định danh sinh từ tên. Chỉ gồm chữ không dấu, chữ số, dấu gạch dưới."
        : "Đổi định danh thì mọi mục đang trỏ tới mục này đổi theo.",
    }),
    altInput && element("label", { for: "entity-alt", text: "Tên gọi khác, mỗi dòng một tên" }),
    altInput,
    element("h3", { text: "Các câu" }),
    element("p", {
      class: "muted",
      text: "Ô có dấu * là bắt buộc. Câu mang nội dung phải chọn nguồn và ghi vị trí trong nguồn. Gõ vài chữ để tìm nguồn hay mục cần trỏ tới.",
    }),
    rows,
    spec.fields.length
      ? element("button", {
          type: "button",
          class: "add-row",
          text: "Thêm dòng",
          onclick: () => run(async () => (await addRow(blankStatement(spec.fields[0]))).scrollIntoView({ block: "nearest" })),
        })
      : null,
    element("div", { class: "actions" }, [
      element("button", { type: "submit", class: "primary", text: "Lưu" }),
      isNew ? null : element("button", { type: "button", class: "danger", text: "Xoá mục", onclick: remove }),
    ]),
    entity.references.length
      ? element("section", { class: "references" }, [
          element("h3", { text: "Đang được trỏ tới từ" }),
          element("ul", {}, entity.references.map((item) => element("li", { text: `${item.label} · ${item.property}` }))),
        ])
      : null,
  ]);
  showEditor(form);
  fitAll(form);
};

// --- sửa một loại (lớp) và các thuộc tính của nó ---------------------------------------

const checkbox = (text, checked, key) => {
  const input = element("input", { type: "checkbox", "data-key": key });
  input.checked = Boolean(checked);
  return { input, label: element("label", { class: "check" }, [input, element("span", { text })]) };
};

const choiceRow = (choice = { id: "", label: "" }) => {
  const idInput = element("input", {
    class: "choice-id",
    spellcheck: "false",
    "aria-label": "Định danh của giá trị",
    placeholder: choice.id || "định danh, sinh từ tên",
    value: choice.id,
  });
  const labelInput = element("input", {
    class: "choice-label",
    "aria-label": "Tên của giá trị",
    placeholder: "Tên hiển thị",
    value: choice.label,
    oninput: () => {
      if (!choice.id) idInput.placeholder = iriName(labelInput.value) || "định danh, sinh từ tên";
    },
  });
  const row = element("div", { class: "choice" }, [labelInput, idInput]);
  row.append(element("button", { type: "button", class: "remove", text: "✕", "aria-label": "Bỏ giá trị này", onclick: () => row.remove() }));
  row.read = () => ({ label: labelInput.value, id: idInput.value.trim() || iriName(labelInput.value) });
  return row;
};

const fieldCard = (field, className) => {
  const isNew = !field.property;
  const card = element("div", { class: "field-card" });
  const nameInput = element("input", {
    "data-key": "name",
    "aria-label": "Tên hiển thị của ô",
    placeholder: "Tên hiển thị, ví dụ hạn nộp",
    value: field.name || "",
    oninput: () => {
      if (isNew) propInput.placeholder = propertyName(nameInput.value) || "định danh, sinh từ tên";
    },
  });
  const propInput = element("input", {
    "data-key": "property",
    "aria-label": "Định danh thuộc tính",
    list: "dl-properties",
    spellcheck: "false",
    placeholder: "định danh, sinh từ tên",
    value: field.property || "",
    disabled: field.locked,
    title: field.locked ? "Mã nguồn của chatbot dùng định danh này nên không đổi được." : "",
    onchange: () => {
      // Chọn một thuộc tính đã có: dùng lại đúng kiểu của nó ở các loại khác.
      const known = state.properties.find((entry) => entry.property === propInput.value.trim());
      if (!isNew || !known) return;
      nameInput.value = known.name;
      kindSelect.value = known.kind;
      targetSelect.value = known.target || "";
      const owner = classSpec(known.classes[0])?.fields.find((item) => item.property === known.property);
      choices.replaceChildren(...(owner?.choices || []).map(choiceRow));
      refresh();
    },
  });
  const kindSelect = element(
    "select",
    { "data-key": "kind", "aria-label": "Kiểu của ô", value: field.kind || "text", onchange: () => refresh() },
    Object.entries(KIND_NAMES).map(([kind, text]) => option(kind, text)),
  );
  const targetSelect = element(
    "select",
    { "data-key": "target", "aria-label": "Loại được trỏ tới", value: field.target || "" },
    [option("", "Trỏ tới loại nào…"), ...state.schema.map((item) => option(item.name, item.label))],
  );
  const required = checkbox("Bắt buộc", field.required, "required");
  const single = checkbox("Chỉ một giá trị", field.single, "single");
  const sourced = element(
    "select",
    { "data-key": "sourced", "aria-label": "Luật gắn nguồn", value: String(field.sourced ?? null) },
    SOURCE_RULES.map(([value, text]) => option(value, text)),
  );
  const choices = element("div", { class: "choices", "data-key": "choices" }, (field.choices || []).map(choiceRow));
  const choiceBox = element("div", { class: "choice-box" }, [
    element("p", { class: "muted", text: "Các giá trị được chọn: tên hiển thị và định danh." }),
    choices,
    element("button", { type: "button", class: "add-row", text: "Thêm giá trị", onclick: () => choices.append(choiceRow()) }),
  ]);
  const shared = element("p", { class: "muted" });
  const refresh = () => {
    targetSelect.hidden = kindSelect.value !== "link";
    choiceBox.hidden = kindSelect.value !== "choice";
    const known = state.properties.find((entry) => entry.property === (propInput.value.trim() || field.property));
    const others = known ? known.classes.filter((name) => name !== className).map((name) => classSpec(name)?.label || name) : [];
    shared.textContent = others.length
      ? `Thuộc tính này dùng chung với: ${others.join(", ")}. Đổi tên hay định danh sẽ đổi ở cả những loại đó.`
      : "";
    shared.hidden = !others.length;
  };
  card.append(
    element("div", { class: "line" }, [
      nameInput,
      propInput,
      element("button", {
        type: "button",
        class: "remove",
        text: "✕",
        title: field.locked ? "Mã nguồn của chatbot dùng ô này nên không bỏ được." : "Bỏ ô này",
        "aria-label": "Bỏ ô này",
        disabled: field.locked,
        onclick: () => card.remove(),
      }),
    ]),
    element("div", { class: "line" }, [kindSelect, targetSelect]),
    element("div", { class: "rules" }, [required.label, single.label, sourced]),
    choiceBox,
    shared,
  );
  card.read = () => {
    const kind = kindSelect.value;
    return {
      was: isNew ? null : field.property,
      property: propInput.value.trim() || propertyName(nameInput.value),
      name: nameInput.value,
      kind,
      target: kind === "link" ? targetSelect.value : null,
      required: required.input.checked,
      single: single.input.checked,
      sourced: JSON.parse(sourced.value),
      choices: kind === "choice" ? [...choices.querySelectorAll(".choice")].map((row) => row.read()) : [],
    };
  };
  refresh();
  return card;
};

const renderClassEditor = (spec) => {
  const isNew = !spec;
  document.getElementById("dl-properties")?.remove();
  document.body.append(
    element(
      "datalist",
      { id: "dl-properties" },
      state.properties.map((entry) => element("option", { value: entry.property, label: `${entry.name} · ${KIND_NAMES[entry.kind]}` })),
    ),
  );
  const nameInput = element("input", {
    "data-where": "name",
    spellcheck: "false",
    value: spec ? spec.name : "",
    placeholder: "định danh, sinh từ tên",
    disabled: spec && spec.locked,
  });
  const labelInput = element("input", {
    "data-where": "label",
    value: spec ? spec.label : "",
    oninput: () => {
      if (isNew) nameInput.placeholder = iriName(labelInput.value) || "định danh, sinh từ tên";
    },
  });
  const alt = checkbox("Mục có ô «tên gọi khác»", spec ? spec.altLabels : true, "altLabels");
  const cards = element("div", { class: "field-cards", "data-where": "fields" }, (spec ? spec.fields : []).map((field) => fieldCard(field, spec.name)));

  let form;
  const showProblems = (details) => {
    clearMarks(form);
    const nodes = [...cards.querySelectorAll(".field-card")];
    for (const detail of details) {
      if (Number.isInteger(detail.field)) {
        const card = nodes[detail.field];
        mark(card?.querySelector(`[data-key="${detail.key}"]`) || card, detail.message);
      } else if (detail.where) mark(form.querySelector(`[data-where="${detail.where}"]`), detail.message);
    }
    focusFirstMark(form);
  };
  const submit = async (confirm) => {
    const payload = {
      name: nameInput.value.trim() || iriName(labelInput.value),
      label: labelInput.value,
      altLabels: alt.input.checked,
      version: spec ? spec.version : undefined,
      confirm,
      fields: [...cards.querySelectorAll(".field-card")].map((card) => card.read()),
    };
    clearMarks(form);
    showStatus("Đang kiểm tra toàn bộ dữ liệu với lược đồ mới và lưu…");
    try {
      const { name } = isNew
        ? await api("/classes", { method: "POST", body: payload })
        : await api(`/classes/${encode(spec.name)}`, { method: "PUT", body: payload });
      clearOptions();
      await loadSchema();
      await selectClass(name, { keepEditor: true });
      renderClassEditor(classSpec(name));
      showStatus("Đã lưu loại.", [], "ok");
    } catch (error) {
      if (error.confirm && window.confirm(`${error.message}\n\n${error.errors.join("\n")}\n\nVẫn lưu?`)) return submit(true);
      showProblems(error.details || []);
      throw error;
    }
  };
  const remove = () =>
    run(async () => {
      if (!window.confirm(`Xoá loại «${spec.label}»? Việc này không hoàn tác được.`)) return;
      await api(`/classes/${encode(spec.name)}?version=${encode(spec.version)}`, { method: "DELETE" });
      clearOptions();
      await loadSchema();
      state.className = null;
      renderClasses();
      $("#list-panel").hidden = true;
      $("#editor").hidden = true;
      showStatus("Đã xoá loại.", [], "ok");
    });

  form = element(
    "form",
    {
      class: "entity-form class-form",
      novalidate: true,
      onsubmit: (event) => {
        event.preventDefault();
        run(() => submit(false));
      },
    },
    [
      element("h2", { text: isNew ? "Thêm loại mới" : `Sửa loại: ${spec.label}` }),
      element("p", {
        class: "muted",
        text: isNew
          ? "Loại là một lớp của ontology; mỗi ô là một thuộc tính của lớp."
          : `${spec.count} mục thuộc loại này. Đổi định danh loại hay thuộc tính thì mọi câu đang dùng đổi theo; toàn bộ dữ liệu được kiểm lại trước khi lưu.`,
      }),
      element("div", { class: "two" }, [
        element("label", {}, [element("span", { text: "Tên loại" }), labelInput]),
        element("label", {}, [element("span", { text: "Định danh (IRI)" }), nameInput]),
      ]),
      spec && spec.locked
        ? element("p", { class: "muted", text: "Mã nguồn của chatbot dùng định danh loại này nên không đổi hay xoá được; tên và các ô vẫn sửa được." })
        : null,
      alt.label,
      element("h3", { text: "Các ô (thuộc tính)" }),
      element("p", {
        class: "muted",
        text: "Chữ, số, ngày, địa chỉ web là thuộc tính dữ liệu; «Trỏ tới một mục» là thuộc tính đối tượng. Định danh để trống thì sinh từ tên.",
      }),
      cards,
      element("button", {
        type: "button",
        class: "add-row",
        text: "Thêm ô",
        onclick: () => {
          const card = fieldCard({ kind: "text", sourced: true }, spec ? spec.name : null);
          cards.append(card);
          card.querySelector("input").focus();
        },
      }),
      element("div", { class: "actions" }, [
        element("button", { type: "submit", class: "primary", text: isNew ? "Tạo loại" : "Lưu loại" }),
        !isNew && !spec.locked ? element("button", { type: "button", class: "danger", text: "Xoá loại", onclick: remove }) : null,
        element("button", { type: "button", text: "Đóng", onclick: () => ($("#editor").hidden = true) }),
      ]),
    ],
  );
  showEditor(form);
};

// --- khởi động --------------------------------------------------------------------

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
$("#edit-class-btn").addEventListener("click", () => run(async () => renderClassEditor(classSpec(state.className))));
$("#new-class-btn").addEventListener("click", () => run(async () => renderClassEditor(null)));
try {
  document.body.classList.toggle("light-theme", localStorage.getItem("themeColor") === "light_mode");
} catch {
  // Không đọc được lựa chọn giao diện thì dùng nền tối mặc định.
}
start();
