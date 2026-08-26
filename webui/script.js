const container = document.querySelector(".container");
const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = document.querySelector(".prompt-input");
const sendButton = document.querySelector("#send-prompt-btn");
const stopButton = document.querySelector("#stop-response-btn");
const themeToggleButton = document.querySelector("#theme-toggle-btn");
const deleteButton = document.querySelector("#delete-chats-btn");
const serverStatus = document.querySelector(".server-status");
const connectionCountdown = document.querySelector(".connection-countdown");
const responseAnnouncer = document.querySelector("#response-announcer");

const apiUrl = (path) => `/api${path}`;

// Khoá sai thì thử lại bao nhiêu lần cũng vẫn sai, nên hai mã này phải tách khỏi
// nhóm lỗi tạm thời để vòng đánh thức dừng ngay thay vì đợi hết ba phút.
const isRejectedKey = (status) => status === 401 || status === 403;
const MAX_HISTORY_MESSAGES = 20;
const HEALTH_DEADLINE_MS = 180_000;
const HEALTH_REQUEST_TIMEOUT_MS = 12_000;
const HEALTH_WAITS_MS = [1_000, 2_000, 4_000, 8_000];
const CONNECTION_COUNTDOWN_SECONDS = 15;

let responseController;
let healthCheckPromise;
let connectionCountdownTimer;
let serverState;
let lastReadyAt = 0;
const chatHistory = [];

const isLightTheme = localStorage.getItem("themeColor") === "light_mode";
document.body.classList.toggle("light-theme", isLightTheme);
themeToggleButton.textContent = isLightTheme ? "dark_mode" : "light_mode";

const isResponding = () => document.body.classList.contains("bot-responding");

const updateControls = () => {
  sendButton.disabled =
    serverState !== "ready" || isResponding() || !promptInput.value.trim();
  deleteButton.disabled = !document.body.classList.contains("chats-active");
};

const stateLabels = {
  waking: "Đang kết nối máy chủ",
  ready: "Máy chủ sẵn sàng",
  offline: "Thiết bị đang mất kết nối mạng.",
  down: "Chưa kết nối được máy chủ. Hãy thử lại sau ít phút.",
  blocked: "Máy chủ từ chối xác thực dịch vụ của trang này.",
};

const stopConnectionCountdown = () => {
  window.clearInterval(connectionCountdownTimer);
  connectionCountdownTimer = undefined;
  connectionCountdown.textContent = "";
};

const startConnectionCountdown = () => {
  stopConnectionCountdown();
  let secondsRemaining = CONNECTION_COUNTDOWN_SECONDS;
  connectionCountdown.textContent = ` (${secondsRemaining})`;
  connectionCountdownTimer = window.setInterval(() => {
    secondsRemaining -= 1;
    connectionCountdown.textContent =
      secondsRemaining >= 0 ? ` (${secondsRemaining})` : "…";
    if (secondsRemaining < 0) {
      window.clearInterval(connectionCountdownTimer);
      connectionCountdownTimer = undefined;
    }
  }, 1_000);
};

const setServerState = (state, label = stateLabels[state]) => {
  const previousState = serverState;
  serverState = state;
  const labelElement = serverStatus.querySelector(".label");
  // Health probe có thể thất bại nhiều lần trong ba phút. Không ghi lại đúng
  // cùng một nội dung vì role=status sẽ khiến trình đọc màn hình báo lặp.
  if (serverStatus.dataset.state !== state || labelElement.textContent !== label) {
    serverStatus.dataset.state = state;
    labelElement.textContent = label;
  }
  if (state === "waking" && previousState !== "waking") {
    startConnectionCountdown();
  } else if (state !== "waking") {
    stopConnectionCountdown();
  }
  if (state === "ready") lastReadyAt = Date.now();
  updateControls();
};

const sleep = (milliseconds) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const probeHealth = async () => {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), HEALTH_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(apiUrl("/healthz"), {
      cache: "no-store",
      signal: controller.signal,
    });
    if (response.ok) return "ready";
    return isRejectedKey(response.status) ? "blocked" : "waking";
  } catch {
    return "waking";
  } finally {
    window.clearTimeout(timeout);
  }
};

const wakeServer = async () => {
  if (!navigator.onLine) {
    setServerState("offline");
    return false;
  }

  // Một trạng thái ``ready`` cũ không bảo đảm replica còn sống. Mọi vòng probe
  // mới đều đóng nút gửi cho tới khi có câu trả lời mới, tránh gửi chat đúng lúc
  // Dịch vụ đang scale từ 0 lên 1.
  setServerState("waking");
  const deadline = Date.now() + HEALTH_DEADLINE_MS;
  let attempt = 0;

  while (Date.now() < deadline) {
    if (!navigator.onLine) {
      setServerState("offline");
      return false;
    }
    const outcome = await probeHealth();
    // Sự kiện offline có thể tới trong lúc fetch còn bay. Không kiểm lại ở đây
    // thì response cũ sẽ ghi đè trạng thái offline bằng ready/waking.
    if (!navigator.onLine) {
      setServerState("offline");
      return false;
    }
    if (outcome === "ready") {
      setServerState("ready");
      return true;
    }
    if (outcome === "blocked") {
      setServerState("blocked");
      return false;
    }

    setServerState("waking");
    const baseWait = HEALTH_WAITS_MS[Math.min(attempt, HEALTH_WAITS_MS.length - 1)];
    const jitter = Math.round(baseWait * Math.random() * 0.15);
    await sleep(baseWait + jitter);
    attempt += 1;
  }

  // Có thể vừa mất mạng trong nhịp sleep cuối cùng, khi vòng lặp không còn một
  // lần probe kế tiếp để chạy nhánh kiểm tra ở đầu vòng.
  setServerState(navigator.onLine ? "down" : "offline");
  return false;
};

const checkServer = () => {
  if (healthCheckPromise) return healthCheckPromise;
  healthCheckPromise = wakeServer().finally(() => {
    healthCheckPromise = undefined;
  });
  return healthCheckPromise;
};

const createMessageElement = (...classes) => {
  const element = document.createElement("div");
  element.classList.add("message", ...classes);
  return element;
};

const scrollToBottom = () =>
  window.requestAnimationFrame(() =>
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }),
  );

const escapeHtml = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const renderLineContent = (text) => {
  const placeholder = "\uE000";
  const links = [];
  let rendered = text.replace(
    /\[([^\]]+)\]\((https?:\/\/(?:\([^)]*\)|[^()\s])+)\)/g,
    (_, label, url) => {
      links.push(
        `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`,
      );
      return placeholder;
    },
  );
  rendered = escapeHtml(rendered);
  rendered = rendered.replace(/(https?:\/\/[^\s<]+)/g, (match) => {
    const suffix = match.match(/[*_]+$/);
    const url = suffix ? match.slice(0, -suffix[0].length) : match;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>${suffix ? suffix[0] : ""}`;
  });
  rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  rendered = rendered.replace(/(?<![\w*])\*([^*\n]+)\*(?![\w*])/g, "<em>$1</em>");
  let index = 0;
  return rendered.replace(new RegExp(placeholder, "g"), () => links[index++]);
};

const renderRichText = (text) => {
  let html = "";
  for (const raw of String(text).split("\n")) {
    if (/^\s*-{3,}\s*$/.test(raw)) {
      html += "<hr>";
      continue;
    }
    const content = raw.replace(/\s+$/, "");
    if (!content) {
      html += '<div class="reply-line spacer"></div>';
      continue;
    }
    if (/^#{1,6}\s+/.test(content)) {
      html += `<div class="reply-line"><strong>${renderLineContent(content.replace(/^#{1,6}\s+/, ""))}</strong></div>`;
      continue;
    }
    const bullet = content.match(/^(\s*)(?:[-*+\u2022]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      const depth = Math.min(Math.floor(bullet[1].length / 2), 3);
      html += `<div class="reply-line bullet depth-${depth}">${renderLineContent(bullet[2])}</div>`;
      continue;
    }
    html += `<div class="reply-line">${renderLineContent(content)}</div>`;
  }
  return html;
};

const createUserMessage = (text) => {
  const message = createMessageElement("user-message");
  const paragraph = document.createElement("p");
  paragraph.className = "message-text";
  paragraph.textContent = text;
  message.append(paragraph);
  return message;
};

const createBotMessage = () => {
  const message = createMessageElement("bot-message", "loading");
  const avatar = document.createElement("span");
  avatar.className = "avatar material-symbols-rounded";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = "school";
  const text = document.createElement("div");
  text.className = "message-text";
  message.append(avatar, text);
  return message;
};

const generateResponse = async (botMessage, userMessage) => {
  const textElement = botMessage.querySelector(".message-text");
  const controller = new AbortController();
  responseController = controller;
  const historyWasTrimmed = chatHistory.length > MAX_HISTORY_MESSAGES;
  const history = chatHistory.slice(-MAX_HISTORY_MESSAGES).map(({ role, text }) => ({
    role: role === "bot" ? "assistant" : "user",
    content: text,
  }));

  let answer = "";
  let completed = false;
  let notice = historyWasTrimmed
    ? "Cuộc trò chuyện đã dài nên mình chỉ dùng 20 tin nhắn gần nhất."
    : "";
  let progress = "Đang suy nghĩ…";

  const paint = () => {
    const noticeHtml = notice
      ? `<div class="reply-line notice">${escapeHtml(notice)}</div>`
      : "";
    textElement.innerHTML =
      noticeHtml +
      (answer
        ? renderRichText(answer)
        : `<div class="reply-line status">${escapeHtml(progress)}</div>`);
    scrollToBottom();
  };

  const consumeEvent = (chunk) => {
    const line = chunk.split("\n").find((item) => item.startsWith("data: "));
    if (!line) return;
    const event = JSON.parse(line.slice(6));
    const legacyTypes = {
      chu: "text_delta",
      tra_cuu: "lookup_started",
      tra_cuu_xong: "lookup_finished",
      hang_doi: "queued",
      canh_bao: "warning",
      xong: "completed",
      loi: "error",
    };
    const eventType = event.type || legacyTypes[event.loai];
    const content = event.content ?? event.noi_dung;
    if (eventType === "text_delta") {
      answer += content;
      botMessage.classList.remove("loading");
    } else if (eventType === "lookup_started") {
      progress = `Đang tra cứu: ${event.keywords ?? event.tu_khoa}`;
    } else if (eventType === "lookup_finished") {
      progress = "Đang viết câu trả lời…";
    } else if (eventType === "queued") {
      progress = `Hệ thống đang bận, bạn đứng thứ ${event.position ?? event.vi_tri} trong hàng chờ…`;
    } else if (eventType === "warning") {
      notice = content;
    } else if (eventType === "completed") {
      completed = true;
      if (!answer) answer = content;
    } else if (eventType === "error") {
      throw new Error(content);
    }
    paint();
  };

  paint();
  try {
    const response = await fetch(apiUrl("/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMessage, history }),
      signal: controller.signal,
    });
    if (!response.ok) {
      if (isRejectedKey(response.status)) {
        setServerState("blocked");
        throw new Error(stateLabels.blocked);
      }
      const detail = await response.json().catch(() => ({}));
      const error = new Error(detail.detail || `Máy chủ trả về lỗi ${response.status}.`);
      error.mayBeCold = [502, 503, 504].includes(response.status);
      throw error;
    }
    if (!response.body) throw new Error("Máy chủ không trả về luồng dữ liệu.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      chunks.forEach(consumeEvent);
    }
    if (buffer.trim()) consumeEvent(buffer);
    if (!completed) {
      const error = new Error(
        "Kết nối tới máy chủ bị gián đoạn trước khi câu trả lời hoàn tất.",
      );
      error.mayBeCold = true;
      error.streamInterrupted = true;
      throw error;
    }
    // Chỉ ghi lượt hoàn tất vào ngữ cảnh. Nếu backend vừa scale về 0 hoặc
    // người dùng bấm dừng, lần thử sau không bị thấy một câu hỏi "mồ côi" mà
    // trợ lý chưa từng trả lời.
    if (answer) {
      chatHistory.push(
        { role: "user", text: userMessage },
        { role: "bot", text: answer },
      );
      responseAnnouncer.textContent = "Đã có câu trả lời mới.";
    }
  } catch (error) {
    const aborted = error.name === "AbortError";
    textElement.textContent = aborted
      ? "Đã dừng phản hồi."
      : error.streamInterrupted
        ? `${error.message} Mình đang kết nối lại máy chủ.`
        : error.mayBeCold || error instanceof TypeError
        ? "Máy chủ có thể vừa chuyển về 0 replica. Mình đang đánh thức lại; bạn gửi lại câu hỏi khi trạng thái chuyển sang sẵn sàng."
        : error.message;
    textElement.style.color = "var(--danger)";
    responseAnnouncer.textContent = textElement.textContent;
    if (!aborted && (error.mayBeCold || error instanceof TypeError)) {
      // Nếu người dùng đã bắt đầu soạn câu kế tiếp thì không ghi đè. Nếu ô còn
      // trống, trả câu vừa lỗi lại để họ chỉ cần bấm gửi sau khi server xanh.
      if (!promptInput.value.trim()) promptInput.value = userMessage;
      setServerState("waking");
      void checkServer();
    }
  } finally {
    botMessage.classList.remove("loading");
    // Lượt cũ có thể hoàn tất abort sau khi người dùng đã xóa và bắt đầu lượt
    // mới. Nó chỉ được mở UI/xóa controller nếu vẫn là lượt đang hoạt động.
    if (responseController === controller) {
      document.body.classList.remove("bot-responding");
      responseController = undefined;
    }
    updateControls();
    scrollToBottom();
  }
};

const handleFormSubmit = (event) => {
  event.preventDefault();
  const userMessage = promptInput.value.trim();
  if (!userMessage || isResponding()) return;
  if (serverState !== "ready") {
    void checkServer();
    return;
  }

  promptInput.value = "";
  document.body.classList.add("chats-active", "bot-responding");
  chatsContainer.append(createUserMessage(userMessage));
  const botMessage = createBotMessage();
  chatsContainer.append(botMessage);
  updateControls();
  scrollToBottom();
  void generateResponse(botMessage, userMessage);
};

promptForm.addEventListener("submit", handleFormSubmit);
promptInput.addEventListener("input", updateControls);

stopButton.addEventListener("click", () => responseController?.abort());

themeToggleButton.addEventListener("click", () => {
  const light = document.body.classList.toggle("light-theme");
  localStorage.setItem("themeColor", light ? "light_mode" : "dark_mode");
  themeToggleButton.textContent = light ? "dark_mode" : "light_mode";
});

deleteButton.addEventListener("click", () => {
  responseController?.abort();
  chatHistory.length = 0;
  chatsContainer.replaceChildren();
  document.body.classList.remove("chats-active", "bot-responding");
  updateControls();
  promptInput.focus();
});

document.querySelectorAll(".suggestions-item").forEach((item) => {
  item.addEventListener("click", () => {
    if (isResponding()) return;
    promptInput.value = item.querySelector(".text").textContent;
    updateControls();
    if (serverState === "ready") {
      promptForm.requestSubmit();
    } else {
      promptInput.focus();
      void checkServer();
    }
  });
});

window.addEventListener("online", () => void checkServer());
window.addEventListener("offline", () => setServerState("offline"));
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || isResponding()) return;
  if (Date.now() - lastReadyAt > 30_000) void checkServer();
});

setServerState("waking");
void checkServer();
