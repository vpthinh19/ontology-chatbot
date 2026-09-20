// Bộ hiển thị markdown chạy trên toàn bộ câu trả lời thật của lượt đo 70 câu: gặp câu nào hiển thị
// sai ngoài thực tế thì thêm câu đó vào đây.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { JSDOM } from "jsdom";

const { window } = new JSDOM("");
globalThis.window = window;
const { renderMarkdown } = await import("../markdown.js");

const RESULTS = new URL("../../resources/end-to-end/heldout/", import.meta.url);
const answers = readdirSync(RESULTS)
  .filter((name) => /^results-\d+\.json$/.test(name))
  .flatMap((name) => JSON.parse(readFileSync(new URL(name, RESULTS), "utf-8")))
  .map((result) => result.tra_loi)
  .filter(Boolean);

const shown = (markdown) => {
  const node = window.document.createElement("div");
  node.innerHTML = renderMarkdown(markdown);
  return node;
};

test("every real answer renders without raw markdown on screen", () => {
  assert.ok(answers.length >= 200);
  for (const answer of answers) {
    const text = shown(answer).textContent;
    for (const raw of ["**", "](http", "`", "$\\", "\\ge", "\\times"]) {
      assert.ok(!text.includes(raw), `«${raw}» còn thô trong: ${answer.slice(0, 120)}`);
    }
  }
});

test("numbered steps keep their numbers and indented bullets nest", () => {
  const node = shown("Các bước:\n1. Nộp đơn\n2. Chờ duyệt\n\n* Hồ sơ:\n    * Đơn\n    * Bản sao");

  assert.deepEqual([...node.querySelectorAll("ol > li")].map((li) => li.textContent), ["Nộp đơn", "Chờ duyệt"]);
  assert.equal(node.querySelectorAll("ul ul > li").length, 2);
});

test("lines the model breaks stay on separate lines", () => {
  assert.equal(shown("Dòng một\nDòng hai").querySelectorAll("br").length, 1);
});

test("links open in a new tab and nothing from the model can run", () => {
  const node = shown(
    '[Quy chế](https://ntu.edu.vn/a_(b)) và https://sinhvien.ntu.edu.vn\n\n<script>alert(1)</script><img src=x onerror=alert(1)>[x](javascript:alert(1))',
  );

  const links = [...node.querySelectorAll("a")];
  assert.deepEqual(links.map((a) => a.getAttribute("href")).filter(Boolean), [
    "https://ntu.edu.vn/a_(b)",
    "https://sinhvien.ntu.edu.vn",
  ]);
  assert.ok(links.filter((a) => a.getAttribute("href")).every((a) => a.target === "_blank" && a.rel === "noopener noreferrer"));
  assert.equal(node.querySelector("script, img, [onerror]"), null);
  assert.ok(links.every((a) => !(a.getAttribute("href") || "").toLowerCase().startsWith("javascript")));
});

test("simple formulas become symbols", () => {
  assert.equal(shown("Điểm $\\ge 140$ và $A = \\Sigma a_i \\times n_i$").textContent.trim(), "Điểm ≥ 140 và A = Σ a_i × n_i");
});

test("a link the model only called \"Link\" is shown as Nguồn", () => {
  const node = shown("Xem ([Link](https://ntu.edu.vn/a)) và [khoản 1 Điều 11 Quy chế](https://ntu.edu.vn/b)");

  const links = [...node.querySelectorAll("a")];
  assert.deepEqual(links.map((a) => a.textContent), ["Nguồn", "khoản 1 Điều 11 Quy chế"]);
  // Đường dẫn không đổi, chỉ chữ hiện lên mới đổi.
  assert.deepEqual(links.map((a) => a.getAttribute("href")), ["https://ntu.edu.vn/a", "https://ntu.edu.vn/b"]);
});
