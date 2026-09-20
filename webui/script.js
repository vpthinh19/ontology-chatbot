// Trang hỏi đáp: gửi câu hỏi kèm lịch sử, đọc câu trả lời chảy về (server-sent events) và vẽ dần.
import { mountAccount } from "./account.js";
import { renderMarkdown } from "./markdown.js";
import { apiUrl, isRejectedKey, REJECTED_KEY_TEXT, warmUp } from "./backend.js";
import { applySavedTheme, toggleTheme } from "./theme.js";

// Tên biểu tượng Material Symbols; mọi tên phải có trong icon_names của index.html.
const ICON = { light: "light_mode", dark: "dark_mode", avatar: "school" };
const MAX_HISTORY_MESSAGES = 20;
// Chỗ chữ đang chờ được nhả hết trong chừng này, nên chữ hiện đều tay thay vì nhảy theo cụm.
// Đo trên trang thật (Việt Nam qua Vercel tới Cloud Run): đường truyền gom các cụm nhỏ của mô hình
// thành cục 15-140 ký tự cách nhau 80-500 ms, nên 120 ms là quá ngắn để trải một cục ra.
const SMOOTH_MS = 400;
// Chỉ tự cuộn theo câu trả lời khi người đọc đang cách đáy không quá chừng này.
const SCROLL_STICK_THRESHOLD_PX = 64;
const INTRODUCTION = [
  "Xin chào, mình là trợ lý học vụ của Trường Đại học Nha Trang. Mình trả lời dựa trên văn bản và trang thông tin chính thức của Trường, kèm nguồn để bạn đối chiếu.",
  "",
  "Bạn có thể hỏi về:",
  "- quy chế đào tạo: khối lượng học tập, điểm và xếp loại, cảnh báo học tập, thôi học, tốt nghiệp;",
  "- thủ tục học vụ và biểu mẫu: nghỉ học tạm thời, chuyển ngành, chuyển trường, xin giấy xác nhận…;",
  "- học phí, học bổng, điểm rèn luyện, chuẩn đầu ra ngoại ngữ và tin học;",
  "- ngành, chương trình đào tạo, các phòng, khoa và thông tin liên hệ.",
  "",
  "Mình không xem được dữ liệu của riêng bạn như điểm, lịch học hay công nợ học phí. Khi nguồn chưa có thông tin, mình sẽ nói rõ thay vì đoán.",
  "",
  "Câu hỏi và câu trả lời được lưu lại để cải thiện hệ thống, vì vậy bạn đừng nhập thông tin cá nhân như mã số sinh viên hay số điện thoại.",
].join("\n");

const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = document.querySelector(".prompt-input");
const sendButton = document.querySelector("#send-prompt-btn");
const stopButton = document.querySelector("#stop-response-btn");
const themeToggleButton = document.querySelector("#theme-toggle-btn");
const deleteButton = document.querySelector("#delete-chats-btn");
const responseAnnouncer = document.querySelector("#response-announcer");

// --- cuộn theo câu trả lời ---------------------------------------------------------

// Bám đáy khi chữ đang chảy, trừ khi người đọc đã kéo lên đọc đoạn trên.
const scroller = {
  following: true,
  jump(behavior) {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior });
  },
  // Sau thao tác của người dùng (vừa gửi câu hỏi): về đáy và bám lại.
  toBottom() {
    this.following = true;
    window.requestAnimationFrame(() => this.jump("smooth"));
  },
  // Trong lúc chữ chảy: cuộn tức thì, vì hoạt ảnh bị khởi động lại mỗi khung hình làm trang giật.
  follow() {
    if (this.following) this.jump("auto");
  },
};
window.addEventListener(
  "scroll",
  () => {
    const gap = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
    scroller.following = gap <= SCROLL_STICK_THRESHOLD_PX;
  },
  { passive: true },
);

// --- tin nhắn ----------------------------------------------------------------------

const messageElement = (...classes) => {
  const element = document.createElement("div");
  element.classList.add("message", ...classes);
  return element;
};

const botMessage = (...classes) => {
  const message = messageElement("bot-message", ...classes);
  const avatar = document.createElement("span");
  avatar.className = "avatar material-symbols-rounded";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = ICON.avatar;
  const text = document.createElement("div");
  text.className = "message-text";
  message.append(avatar, text);
  return message;
};

const userMessage = (text) => {
  const message = messageElement("user-message");
  const paragraph = document.createElement("p");
  paragraph.className = "message-text";
  paragraph.textContent = text;
  message.append(paragraph);
  return message;
};

const showIntroduction = () => {
  const message = botMessage("introduction");
  message.querySelector(".message-text").innerHTML = renderMarkdown(INTRODUCTION);
  chatsContainer.append(message);
};

// Một câu trả lời đang được vẽ. Chữ về nhanh hơn nhịp vẽ của màn hình, nên mọi mảnh tới trong cùng
// một khung hình gộp thành một lần vẽ.
class AnswerView {
  constructor(message) {
    this.message = message;
    this.text = message.querySelector(".message-text");
    //: phần đã hiện trên màn hình, và phần đã nhận nhưng còn chờ được nhả ra.
    this.answer = "";
    this.waiting = "";
    this.progress = "Đang suy nghĩ…";
    this.frame = undefined;
    this.lastFrame = 0;
    this.painted = undefined;
  }

  append(text) {
    this.waiting += text;
    this.message.classList.remove("loading");
    this.paint();
  }

  status(text) {
    this.progress = text;
    this.paint();
  }

  // Mô hình trả chữ theo cụm, cụm to nhỏ và cách nhau không đều. Mỗi khung hình chỉ nhả một phần
  // chỗ đang chờ, tính theo thời gian thật nên màn hình 60 hay 120 Hz đều chảy như nhau; chỗ chờ
  // luôn cạn trong khoảng SMOOTH_MS nên chữ không bị tụt lại sau câu trả lời.
  reveal(now) {
    // Khung hình đầu tiên chưa có mốc trước để so: coi như một khung hình, không thì nó nhả sạch
    // cụm chữ đầu tiên và câu trả lời mở đầu bằng một cú phụt.
    const troi_qua = this.lastFrame ? now - this.lastFrame : 16;
    const share = Math.min(1, troi_qua / SMOOTH_MS);
    const take = Math.max(1, Math.ceil(this.waiting.length * share));
    this.answer += this.waiting.slice(0, take);
    this.waiting = this.waiting.slice(take);
    this.lastFrame = now;
  }

  paint() {
    this.frame ??= window.requestAnimationFrame((now) => {
      this.frame = undefined;
      if (this.waiting) this.reveal(now);
      this.render();
      if (this.waiting) this.paint();
    });
  }

  // Vẽ ngay và hết chỗ chờ: khi câu trả lời không đổi nữa, và ở tab ẩn (nơi khung hình không tới).
  renderNow() {
    this.cancel();
    this.answer += this.waiting;
    this.waiting = "";
    this.render();
  }

  render() {
    let html;
    if (this.answer) {
      html = renderMarkdown(this.answer);
    } else {
      const line = document.createElement("div");
      line.className = "reply-line status";
      line.textContent = this.progress;
      html = line.outerHTML;
    }
    if (html !== this.painted) {
      this.text.innerHTML = html;
      this.painted = html;
    }
    scroller.follow();
  }

  fail(text) {
    this.cancel();
    this.text.textContent = text;
    this.text.style.color = "var(--danger)";
  }

  cancel() {
    if (this.frame === undefined) return;
    window.cancelAnimationFrame(this.frame);
    this.frame = undefined;
  }
}

// --- hội thoại ------------------------------------------------------------------------

class StreamError extends Error {
  // ``mayBeCold``: máy chủ có thể vừa ngủ; ``interrupted``: luồng đứt trước sự kiện completed.
  constructor(message, { mayBeCold = false, interrupted = false } = {}) {
    super(message);
    this.mayBeCold = mayBeCold;
    this.interrupted = interrupted;
  }
}

// Lịch sử gửi kèm mỗi câu (máy chủ không giữ phiên) và mã phiên máy chủ cấp để gom các lượt
// trong lịch sử chat. Chỉ lượt hoàn tất mới vào lịch sử.
class Conversation {
  constructor() {
    this.history = [];
    this.session = null;
    this.controller = undefined;
  }

  get responding() {
    return this.controller !== undefined;
  }

  stop() {
    this.controller?.abort();
  }

  clear() {
    this.stop();
    this.controller = undefined;
    this.history.length = 0;
    this.session = null;
  }

  async ask(question, view) {
    const controller = new AbortController();
    this.controller = controller;
    try {
      const answer = await this.stream(question, view, controller.signal);
      if (answer) {
        this.history.push({ role: "user", content: question }, { role: "assistant", content: answer });
      }
      return answer;
    } finally {
      // Lượt cũ có thể kết thúc sau khi người dùng đã xoá hội thoại và bắt đầu lượt mới.
      if (this.controller === controller) this.controller = undefined;
    }
  }

  async stream(question, view, signal) {
    const response = await fetch(apiUrl("/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        history: this.history.slice(-MAX_HISTORY_MESSAGES),
        ...(this.session ? { session: this.session } : {}),
      }),
      signal,
    });
    this.session = response.headers.get("X-Chat-Session") || this.session;
    if (!response.ok) {
      if (isRejectedKey(response.status)) {
        throw new StreamError(REJECTED_KEY_TEXT);
      }
      const detail = await response.json().catch(() => ({}));
      throw new StreamError(detail.detail || `Máy chủ trả về lỗi ${response.status}.`, {
        mayBeCold: [502, 503, 504].includes(response.status),
      });
    }
    if (!response.body) throw new StreamError("Máy chủ không trả về luồng dữ liệu.");

    let answer = "";
    let completed = false;
    const consume = (chunk) => {
      const line = chunk.split("\n").find((item) => item.startsWith("data: "));
      if (!line) return;
      const event = JSON.parse(line.slice(6));
      if (event.type === "text_delta") {
        answer += event.content;
        view.append(event.content);
      } else if (event.type === "lookup_started") {
        view.status(`Đang tra cứu: ${event.keywords}`);
      } else if (event.type === "lookup_finished") {
        view.status("Đang viết câu trả lời…");
      } else if (event.type === "queued") {
        view.status(`Hệ thống đang bận, bạn đứng thứ ${event.position} trong hàng chờ…`);
      } else if (event.type === "completed") {
        completed = true;
        if (!answer) {
          answer = event.content;
          view.append(event.content);
        }
      } else if (event.type === "error") {
        throw new StreamError(event.content);
      }
    };

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      chunks.forEach(consume);
    }
    if (buffer.trim()) consume(buffer);
    view.renderNow();
    if (!completed) {
      throw new StreamError("Kết nối tới máy chủ bị gián đoạn trước khi câu trả lời hoàn tất.", {
        mayBeCold: true,
        interrupted: true,
      });
    }
    return answer;
  }
}

// --- nối giao diện ----------------------------------------------------------------------

const conversation = new Conversation();

const updateControls = () => {
  sendButton.disabled = conversation.responding || !promptInput.value.trim();
  deleteButton.disabled = !document.body.classList.contains("chats-active");
};


const failureText = (error) => {
  if (error.name === "AbortError") return "Đã dừng phản hồi.";
  if (error.interrupted) return `${error.message} Mình đang kết nối lại máy chủ.`;
  if (error.mayBeCold || error instanceof TypeError) {
    return "Máy chủ vừa tạm nghỉ và đang được đánh thức lại, bạn gửi lại câu hỏi sau một chút nhé.";
  }
  return error.message;
};

const send = async (question) => {
  document.body.classList.add("chats-active", "bot-responding");
  chatsContainer.append(userMessage(question));
  const view = new AnswerView(botMessage("loading"));
  chatsContainer.append(view.message);
  view.renderNow();
  updateControls();
  scroller.toBottom();
  try {
    if (await conversation.ask(question, view)) responseAnnouncer.textContent = "Đã có câu trả lời mới.";
  } catch (error) {
    view.fail(failureText(error));
    responseAnnouncer.textContent = view.text.textContent;
    if (error.name !== "AbortError" && (error.mayBeCold || error instanceof TypeError)) {
      // Trả câu vừa lỗi lại ô nhập để gửi lại, trừ khi người dùng đã gõ câu khác.
      if (!promptInput.value.trim()) promptInput.value = question;
      // Câu vừa lỗi có thể là câu đánh thức máy chủ: hích thêm một lượt để lần gửi lại đã có máy sẵn.
      warmUp();
    }
  } finally {
    view.message.classList.remove("loading");
    if (!conversation.responding) document.body.classList.remove("bot-responding");
    updateControls();
    scroller.follow();
  }
};

promptForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = promptInput.value.trim();
  if (!question || conversation.responding) return;
  promptInput.value = "";
  void send(question);
});
promptInput.addEventListener("input", updateControls);
stopButton.addEventListener("click", () => conversation.stop());

applySavedTheme();
const showThemeIcon = () => {
  themeToggleButton.textContent = document.body.classList.contains("light-theme") ? ICON.dark : ICON.light;
};
showThemeIcon();
themeToggleButton.addEventListener("click", () => {
  toggleTheme();
  showThemeIcon();
});

deleteButton.addEventListener("click", () => {
  conversation.clear();
  chatsContainer.replaceChildren();
  showIntroduction();
  document.body.classList.remove("chats-active", "bot-responding");
  updateControls();
  promptInput.focus();
});

// Tab quay lại sau một lúc thì máy chủ có thể đã ngủ: hích lại để lúc gửi câu hỏi máy đã lên.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !conversation.responding) warmUp();
});

showIntroduction();
warmUp();

mountAccount(document.querySelector("#account"), { other: { href: "/admin", label: "Quản trị" } });
