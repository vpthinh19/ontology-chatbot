// Form sửa một lớp và các thuộc tính của nó; máy chủ kiểm lại toàn bộ dữ liệu với lược đồ mới trước khi lưu.
import { api } from "./api.js";
import { classSpec, clearOptions, state } from "./schema.js";
import {
  $,
  checkbox,
  clearMarks,
  element,
  encode,
  focusFirstMark,
  iriName,
  mark,
  option,
  propertyName,
  run,
  showEditor,
  showStatus,
} from "./ui.js";

const KIND_NAMES = {
  text: "Chữ (tiếng Việt)",
  string: "Chuỗi ký tự (mã, số hiệu, email…)",
  integer: "Số nguyên",
  decimal: "Số thập phân",
  date: "Ngày",
  uri: "Địa chỉ web",
  link: "Trỏ tới một thực thể (thuộc tính đối tượng)",
  choice: "Chọn trong danh sách",
};
const SOURCE_RULES = [
  ["true", "Bắt buộc có nguồn"],
  ["false", "Có thể có nguồn"],
  ["null", "Không gắn nguồn"],
];

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
    "aria-label": "Tên hiển thị của thuộc tính",
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
    { "data-key": "kind", "aria-label": "Kiểu giá trị", value: field.kind || "text", onchange: () => refresh() },
    Object.entries(KIND_NAMES).map(([kind, text]) => option(kind, text)),
  );
  const targetSelect = element(
    "select",
    { "data-key": "target", "aria-label": "Lớp được trỏ tới", value: field.target || "" },
    [option("", "Trỏ tới lớp nào…"), ...state.schema.map((item) => option(item.name, item.label))],
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
      ? `Thuộc tính này dùng chung với: ${others.join(", ")}. Đổi tên hay định danh sẽ đổi ở cả những lớp đó.`
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
        title: field.locked ? "Mã nguồn của chatbot dùng thuộc tính này nên không bỏ được." : "Bỏ thuộc tính này",
        "aria-label": "Bỏ thuộc tính này",
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

// ``spec``: lớp đang sửa, ``null`` khi tạo mới. ``nav.saved(định danh)`` và ``nav.deleted()`` cho trang
// chuyển tới lớp vừa lưu, hoặc đóng danh sách.
export const renderClassEditor = (spec, nav) => {
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
  const alt = checkbox("Thực thể có tên gọi khác", spec ? spec.altLabels : true, "altLabels");
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
      await nav.saved(name);
      showStatus("Đã lưu lớp.", [], "ok");
    } catch (error) {
      if (error.confirm && window.confirm(`${error.message}\n\n${error.errors.join("\n")}\n\nVẫn lưu?`)) return submit(true);
      showProblems(error.details || []);
      throw error;
    }
  };
  const remove = () =>
    run(async () => {
      if (!window.confirm(`Xoá lớp «${spec.label}»? Việc này không hoàn tác được.`)) return;
      await api(`/classes/${encode(spec.name)}?version=${encode(spec.version)}`, { method: "DELETE" });
      clearOptions();
      await nav.deleted();
      showStatus("Đã xoá lớp.", [], "ok");
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
      element("h2", { text: isNew ? "Thêm lớp mới" : `Sửa lớp: ${spec.label}` }),
      element("p", {
        class: "muted",
        text: isNew
          ? "Mỗi lớp có một tập thuộc tính; thực thể của lớp chỉ nhận các thuộc tính đó."
          : `${spec.count} thực thể thuộc lớp này. Đổi định danh lớp hay thuộc tính thì mọi quan hệ đang dùng đổi theo; toàn bộ dữ liệu được kiểm lại trước khi lưu.`,
      }),
      element("div", { class: "two" }, [
        element("label", {}, [element("span", { text: "Tên lớp" }), labelInput]),
        element("label", {}, [element("span", { text: "Định danh (IRI)" }), nameInput]),
      ]),
      spec && spec.locked
        ? element("p", { class: "muted", text: "Mã nguồn của chatbot dùng định danh lớp này nên không đổi hay xoá được; tên và các thuộc tính vẫn sửa được." })
        : null,
      alt.label,
      element("h3", { text: "Các thuộc tính" }),
      element("p", {
        class: "muted",
        text: "Chữ, số, ngày, địa chỉ web là thuộc tính dữ liệu; «Trỏ tới một thực thể» là thuộc tính đối tượng. Định danh để trống thì sinh từ tên.",
      }),
      cards,
      element("button", {
        type: "button",
        class: "add-row",
        text: "Thêm thuộc tính",
        onclick: () => {
          const card = fieldCard({ kind: "text", sourced: true }, spec ? spec.name : null);
          cards.append(card);
          card.querySelector("input").focus();
        },
      }),
      element("div", { class: "actions" }, [
        element("button", { type: "submit", class: "primary", text: isNew ? "Tạo lớp" : "Lưu lớp" }),
        !isNew && !spec.locked ? element("button", { type: "button", class: "danger", text: "Xoá lớp", onclick: remove }) : null,
        element("button", { type: "button", text: "Đóng", onclick: () => ($("#editor").hidden = true) }),
      ]),
    ],
  );
  showEditor(form);
};
