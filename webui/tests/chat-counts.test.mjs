// Hai con số trên nhãn phiên phải đếm giống hệt máy chủ (_session_summary trong runtime/chatlog.py),
// vì sau khi lưu xem xét trang tự đếm lại thay vì hỏi lại cả danh sách.
import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;

const { sessionCounts } = await import("../admin-page/chats.js");

const turn = (state, flags = []) => ({ flags, review: { state, note: "" } });

test("counts the turns marked as needing data", () => {
  const counts = sessionCounts([turn("can-bo-sung"), turn("da-xu-ly"), turn(""), turn("can-bo-sung")]);

  assert.equal(counts.turns, 4);
  assert.equal(counts.todo, 2);
});

test("a turn counts as open when it has a flag and nobody has reviewed it", () => {
  const counts = sessionCounts([
    turn("", ["says_missing"]),   // có dấu hiệu, chưa ai xem
    turn("bo-qua", ["says_missing"]), // đã xem rồi
    turn("", []),                 // không có dấu hiệu gì
  ]);

  assert.equal(counts.open, 1);
  assert.equal(counts.todo, 0);
});

test("an empty session counts as zero everywhere", () => {
  assert.deepEqual(sessionCounts([]), { turns: 0, todo: 0, open: 0 });
});
