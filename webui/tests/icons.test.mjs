// Font biểu tượng chỉ chứa các tên trong icon_names của index.html: biểu tượng nào trang dùng mà thiếu
// tên ở đó sẽ hiện thành chữ (ví dụ "delete") thay vì hình.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (name) => readFileSync(new URL(`../${name}`, import.meta.url), "utf-8");

test("every icon the chat page shows is in the font subset", () => {
  const html = read("index.html");
  const subset = html.match(/icon_names=([a-z_,]+)/)[1].split(",");
  assert.deepEqual(subset, [...subset].sort(), "Google Fonts cần icon_names xếp theo chữ cái");
  const inHtml = [...html.matchAll(/material-symbols-rounded[^>]*>\s*([a-z_]+)\s*</g)].map((match) => match[1]);
  const icons = read("script.js").match(/const ICON = \{([^}]*)\}/)[1];
  const inScript = [...icons.matchAll(/"([a-z_]+)"/g)].map((match) => match[1]);
  assert.ok(inHtml.length && inScript.length);
  for (const icon of [...inHtml, ...inScript]) assert.ok(subset.includes(icon), `thiếu «${icon}» trong icon_names`);
});
