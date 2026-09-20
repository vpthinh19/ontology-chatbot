// Lịch sử chat theo phiên: danh sách phiên, các lượt của một phiên, trạng thái xem xét và xoá.
import { renderMarkdown } from "../markdown.js";
import { api } from "./api.js";
import { $, element, encode, fitAll, growing, option, run, showStatus } from "./ui.js";

const FLAG_NAMES = {
  not_found: "Tra cứu không ra",
  says_missing: "Không có thông tin",
  out_of_scope: "Ngoài phạm vi",
  no_lookup: "Không tra cứu",
  failed: "Không hoàn tất",
};
const FLAG_TEXT = {
  not_found: "Có lần tra cứu không trả về thực thể nào.",
  says_missing: "Mô hình đánh dấu ontology không có điều được hỏi, cả câu hoặc một phần.",
  out_of_scope: "Mô hình đánh dấu câu hỏi không thuộc phạm vi học vụ.",
  no_lookup: "Trả lời mà không tra cứu lần nào.",
  failed: "Lượt không hoàn tất: quá hạn, lỗi, hàng đợi đầy hoặc người dùng đóng trang.",
};
const REVIEW_NAMES = { "": "Chưa xem xét", "can-bo-sung": "Cần bổ sung", "da-xu-ly": "Đã xử lý", "bo-qua": "Không cần xử lý" };
const OUTCOME_NAMES = {
  ok: "hoàn tất",
  timeout: "quá hạn chờ mô hình",
  "too-many-steps": "vượt số bước tối đa",
  busy: "hàng đợi đầy",
  "queue-timeout": "chờ trong hàng đợi quá lâu",
  "rate-limited": "dịch vụ mô hình quá tải",
  error: "lỗi",
  abandoned: "người dùng đóng trang giữa chừng",
};
// Lịch sử chat theo phiên: danh sách là các phiên (cuộc trò chuyện), mở một phiên thấy mọi lượt của nó;
// xem xét và xoá làm trên từng lượt, hoặc xoá cả phiên.
const chatState = { items: [], openSession: null, turns: [] };
const when = (iso) =>
  iso ? new Date(iso).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "";
const badges = (item) =>
  element("span", { class: "badges" }, [
    item.admin ? element("span", { class: "badge admin", text: "quản trị" }) : null,
    ...(item.flags || []).map((flag) => element("span", { class: "badge warn", text: FLAG_NAMES[flag] || flag })),
    item.todo ? element("span", { class: "badge state", text: `${REVIEW_NAMES["can-bo-sung"]} (${item.todo})` }) : null,
  ]);

const renderChatList = () => {
  const list = $("#chat-items");
  $("#chat-list-title").textContent = `Các phiên (${chatState.items.length})`;
  if (!chatState.items.length) {
    list.replaceChildren(element("li", { class: "muted", text: "Không có phiên nào khớp bộ lọc." }));
    return;
  }
  list.replaceChildren(
    ...chatState.items.map((item) =>
      element(
        "li",
        {},
        element(
          "button",
          {
            type: "button",
            class: item.session === chatState.openSession ? "active" : "",
            onclick: () => run(() => openSession(item.session)),
          },
          [
            element("span", { class: "when", text: `${when(item.time)} · ${item.turns} lượt` }),
            element("span", { class: "question", text: item.question }),
            badges(item),
          ],
        ),
      ),
    ),
  );
};

// Lấy lại từ máy chủ những gì đang mở: dùng khi người khác vừa sửa dữ liệu, hoặc khi muốn chắc.
export const refreshChats = async () => {
  const open = chatState.openSession;
  await loadChats();
  if (open && chatState.items.some((item) => item.session === open)) await openSession(open);
  else closeSession();
};

export const loadChats = async () => {
  const params = new URLSearchParams({
    view: $("#chat-view-select").value,
    days: $("#chat-days").value,
    q: $("#chat-query").value.trim(),
  });
  chatState.items = (await api(`/chats?${params}`)).items;
  renderChatList();
};

const closeSession = () => {
  chatState.openSession = null;
  chatState.turns = [];
  $("#chat-detail").hidden = true;
};

// Hai con số trên nhãn phiên là đếm thuần các lượt của phiên đó (xem _session_summary ở máy chủ), mà
// trang đang giữ đủ các lượt, nên đếm lại tại chỗ cho ra đúng con số ấy: đỡ một lượt hỏi cả danh sách.
export const sessionCounts = (turns) => ({
  turns: turns.length,
  todo: turns.filter((turn) => turn.review?.state === "can-bo-sung").length,
  open: turns.filter((turn) => (turn.flags || []).length && !turn.review?.state).length,
});
const recountSession = (session) => {
  const item = chatState.items.find((entry) => entry.session === session);
  if (item) Object.assign(item, sessionCounts(chatState.turns));
  renderChatList();
};

const turnView = (session, record, index) => {
  const turnPath = `/chats/${encode(session)}/${encode(record.id)}`;
  const note = growing({ "aria-label": "Ghi chú xem xét", placeholder: "Ghi chú: cần bổ sung gì, đã sửa ở đâu…", value: record.review.note || "" });
  const stateSelect = element(
    "select",
    { "aria-label": "Trạng thái xem xét", value: record.review.state || "" },
    Object.entries(REVIEW_NAMES).map(([value, text]) => option(value, text)),
  );
  const saveReview = () =>
    run(async () => {
      const saved = await api(turnPath, { method: "PUT", body: { state: stateSelect.value, note: note.value } });
      chatState.turns = chatState.turns.map((turn) => (turn.id === record.id ? saved : turn));
      recountSession(session);
      showSession(session, chatState.turns);
      showStatus("Đã lưu trạng thái xem xét.", [], "ok");
    });
  const remove = () =>
    run(async () => {
      if (!window.confirm("Xoá lượt này? Việc này không hoàn tác được.")) return;
      await api(turnPath, { method: "DELETE" });
      chatState.turns = chatState.turns.filter((turn) => turn.id !== record.id);
      if (chatState.turns.length) {
        recountSession(session);
        showSession(session, chatState.turns);
      } else {
        chatState.items = chatState.items.filter((item) => item.session !== session);
        closeSession();
        renderChatList();
      }
      showStatus("Đã xoá lượt.", [], "ok");
    });
  const lookups = (record.lookups || []).map((lookup) =>
    element("div", { class: "lookup" }, [
      element("div", {}, [
        element("b", { text: (lookup.keywords || []).join(" · ") }),
        element("span", {
          text: lookup.status === "found" ? "  · có kết quả" : lookup.status === "not_found" ? "  · không ra thực thể nào" : "",
        }),
      ]),
      lookup.results && lookup.results.length
        ? element("ul", {}, lookup.results.map((label) => element("li", { text: label })))
        : null,
      lookup.unmatched && lookup.unmatched.length
        ? element("p", { class: "muted", text: `Từ khoá không khớp thực thể nào: ${lookup.unmatched.join(", ")}` })
        : null,
    ]),
  );
  return element("section", { class: "chat-turn" }, [
    element("h3", { text: `Lượt ${index + 1} · ${when(record.time)}` }),
    element("p", {
      class: "muted",
      text: `${record.admin ? "Câu quản trị tự hỏi thử · " : ""}Kết quả: ${
        OUTCOME_NAMES[record.outcome] || record.outcome
      } · ${(record.duration_ms / 1000).toFixed(1).replace(".", ",")} giây`,
    }),
    record.flags && record.flags.length
      ? element("ul", { class: "muted" }, record.flags.map((flag) => element("li", { text: FLAG_TEXT[flag] || flag })))
      : null,
    element("p", { class: "said", text: record.question }),
    record.answer
      ? Object.assign(element("div", { class: "said answer" }), { innerHTML: renderMarkdown(record.answer) })
      : element("p", { class: "said", text: "(không có câu trả lời)" }),
    record.error ? element("p", { class: "field-error", text: `Lỗi: ${record.error}` }) : null,
    element("details", {}, [
      element("summary", { text: `Các lần tra cứu (${lookups.length})` }),
      ...(lookups.length ? lookups : [element("p", { class: "muted", text: "Không tra cứu lần nào." })]),
    ]),
    element("div", { class: "review-box" }, [
      stateSelect,
      note,
      record.review.time ? element("p", { class: "muted", text: `Cập nhật lúc ${when(record.review.time)}` }) : null,
      element("div", { class: "actions" }, [
        element("button", { type: "button", class: "primary", text: "Lưu xem xét", onclick: saveReview }),
        element("button", { type: "button", class: "danger", text: "Xoá lượt này", onclick: remove }),
      ]),
    ]),
  ]);
};

const openSession = async (session) => {
  const { turns } = await api(`/chats/${encode(session)}`);
  showSession(session, turns);
};

// Vẽ phiên từ các lượt đang có trong tay. Tách khỏi việc tải để lưu hay xoá một lượt xong thì vẽ lại
// ngay, không phải hỏi máy chủ những gì trang vừa gửi lên.
function showSession(session, turns) {
  chatState.openSession = session;
  chatState.turns = turns;
  renderChatList();
  const removeSession = () =>
    run(async () => {
      if (!window.confirm(`Xoá cả phiên (${turns.length} lượt)? Việc này không hoàn tác được.`)) return;
      await api(`/chats/${encode(session)}`, { method: "DELETE" });
      closeSession();
      // Bỏ phiên khỏi danh sách đang hiện thay vì hỏi lại máy chủ cả danh sách: mỗi lượt gọi tốn
      // khoảng nửa giây đường truyền, mà ta đã biết chắc phiên vừa xoá không còn.
      chatState.items = chatState.items.filter((item) => item.session !== session);
      renderChatList();
      showStatus("Đã xoá phiên.", [], "ok");
    });
  const detail = element("div", { class: "chat-record" }, [
    element("div", { class: "session-head" }, [
      element("div", {}, [
        element("h2", { text: `Phiên bắt đầu lúc ${when(turns[0].time)}` }),
        element("p", { class: "muted", text: `${turns.length} lượt · ${session}` }),
      ]),
      element("button", { type: "button", class: "danger", text: "Xoá cả phiên", onclick: removeSession }),
    ]),
    ...turns.map((record, index) => turnView(session, record, index)),
  ]);
  const panel = $("#chat-detail");
  panel.replaceChildren(detail);
  panel.hidden = false;
  panel.scrollTop = 0;
  fitAll(panel);
}
