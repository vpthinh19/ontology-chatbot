// Danh sách mục của một lớp: nhiều dòng trong cùng một form hỏi cùng lúc thì chỉ được gọi máy chủ một lần.
import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;

const { clearOptions, datalistFor, optionsOf, state } = await import("../admin-page/schema.js");

let calls = [];
globalThis.fetch = async (url) => {
  calls.push(url);
  return { ok: true, status: 200, json: async () => ({ items: [{ id: "ThuTucChuyenNganh", label: "Thủ tục chuyển ngành" }] }) };
};

test("rows asking for the same class at the same time share one request", async () => {
  calls = [];
  clearOptions();

  const rows = await Promise.all([optionsOf("Nguon"), optionsOf("Nguon"), optionsOf("Nguon"), optionsOf("Nguon")]);

  assert.equal(calls.length, 1);
  assert.equal(rows[0], rows[3]);
});

test("saving one class forgets that class only", async () => {
  calls = [];
  clearOptions();
  await Promise.all([optionsOf("Nguon"), optionsOf("ThuTucHocVu")]);
  assert.equal(calls.length, 2);

  clearOptions("Nguon");
  await Promise.all([optionsOf("Nguon"), optionsOf("ThuTucHocVu")]);

  assert.equal(calls.length, 3, "chỉ lớp vừa đổi phải hỏi lại máy chủ");
});

test("a datalist is built once per class", async () => {
  calls = [];
  clearOptions();

  const [first, second] = await Promise.all([datalistFor("Nguon"), datalistFor("Nguon")]);

  assert.equal(first, second);
  assert.equal(document.querySelectorAll("datalist[id='dl-Nguon']").length, 1);
  assert.equal(calls.length, 1);
});
