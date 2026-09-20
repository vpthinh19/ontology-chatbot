// Form sửa một thực thể: tên, lớp, định danh, tên gọi khác và các quan hệ (mỗi quan hệ kèm nguồn và vị trí).
import { api } from "./api.js";
import { classSpec, clearOptions, datalistFor, resolve, shown, state } from "./schema.js";
import {
  $,
  clearMarks,
  element,
  encode,
  fitAll,
  focusFirstMark,
  growing,
  iriName,
  lines,
  mark,
  option,
  run,
  showEditor,
  showStatus,
} from "./ui.js";

export const blankStatement = (field) => ({ property: field?.property, value: "", source: null, coordinate: null });
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
  if (field && field.sourced === null) return element("span", { class: "no-source", text: "Thuộc tính này không gắn nguồn" });
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
    if (!field) choices.unshift(option(current.property, `${current.property} (không thuộc lớp này)`));
    const picker = element(
      "select",
      {
        class: "property",
        "aria-label": "Thuộc tính",
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
        title: "Bỏ quan hệ này",
        "aria-label": "Bỏ quan hệ này",
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
          message: `Quan hệ ${row + 1} (${field.name}): không có thực thể «${shown.value.trim()}» trong lớp «${target ? target.label : field.target}»; hãy chọn trong danh sách gợi ý.`,
        });
        continue;
      }
    }
    const source = await resolve("Nguon", shown.source);
    if (source === null) {
      problems.push({ row, message: `Quan hệ ${row + 1}: không có nguồn «${shown.source.trim()}»; hãy chọn trong danh sách gợi ý.` });
      continue;
    }
    statements.push({ row, property: shown.property, value, source: source || null, coordinate: coordinate || null });
  }
  return { statements, problems };
};

// ``nav.saved(lớp, định danh)`` và ``nav.deleted(lớp)``: trang chuyển tới mục vừa lưu, hoặc về danh sách.
export const renderEditor = async (entity, nav) => {
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
          await renderEditor(
            {
              ...entity,
              class: classSelect.value,
              label: labelInput.value,
              altLabels: altInput ? lines(altInput.value) : [],
              statements: [...rows.querySelectorAll(".statement")].map(readRow),
            },
            nav,
          );
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
        clearOptions(payload.class);
        await nav.saved(payload.class, id);
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
      clearOptions(spec.name);
      await nav.deleted(spec.name);
      showStatus("Đã xoá.", [], "ok");
    });

  form = element("form", { class: "entity-form", onsubmit: save, novalidate: true }, [
    element("h2", { text: isNew ? `Thêm thực thể mới: ${spec.label}` : entity.label }),
    element("div", { class: "two" }, [
      element("label", {}, [element("span", { text: "Tên" }), labelInput]),
      element("label", {}, [element("span", { text: "Lớp" }), classSelect]),
    ]),
    element("label", { for: "entity-id", text: "Định danh (IRI)" }),
    idInput,
    element("p", {
      class: "muted",
      text: isNew
        ? "Để trống thì định danh sinh từ tên. Chỉ gồm chữ không dấu, chữ số, dấu gạch dưới."
        : "Đổi định danh thì mọi thực thể đang trỏ tới thực thể này đổi theo.",
    }),
    altInput && element("label", { for: "entity-alt", text: "Tên gọi khác, mỗi dòng một tên" }),
    altInput,
    element("h3", { text: "Các quan hệ" }),
    element("p", {
      class: "muted",
      text: "Thuộc tính có dấu * là bắt buộc. Quan hệ mang nội dung phải có nguồn và vị trí trong nguồn. Gõ vài chữ để tìm nguồn hay thực thể cần trỏ tới.",
    }),
    rows,
    spec.fields.length
      ? element("button", {
          type: "button",
          class: "add-row",
          text: "Thêm quan hệ",
          onclick: () => run(async () => (await addRow(blankStatement(spec.fields[0]))).scrollIntoView({ block: "nearest" })),
        })
      : null,
    element("div", { class: "actions" }, [
      element("button", { type: "submit", class: "primary", text: "Lưu" }),
      isNew ? null : element("button", { type: "button", class: "danger", text: "Xoá thực thể", onclick: remove }),
    ]),
    entity.references.length
      ? element("section", { class: "references" }, [
          element("h3", { text: "Các thực thể trỏ tới thực thể này" }),
          element("ul", {}, entity.references.map((item) => element("li", { text: `${item.label} · ${item.property}` }))),
        ])
      : null,
  ]);
  showEditor(form);
  fitAll(form);
};
