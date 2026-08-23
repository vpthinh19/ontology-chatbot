const container = document.querySelector(".container");
const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = promptForm.querySelector(".prompt-input");
const themeToggleBtn = document.querySelector("#theme-toggle-btn");
// API Setup - local FastAPI backend
const API_URL = "/chat";
// Khớp với hàng rào máy chủ: giao diện vẫn giữ toàn bộ bong bóng để người dùng
// đọc lại, nhưng chỉ gửi mười cặp tin nhắn gần nhất vào lượt kế tiếp.
const MAX_HISTORY_MESSAGES = 20;
let controller;
const chatHistory = [];
const userData = { message: "" };
// Set initial theme from local storage
const isLightTheme = localStorage.getItem("themeColor") === "light_mode";
document.body.classList.toggle("light-theme", isLightTheme);
themeToggleBtn.textContent = isLightTheme ? "dark_mode" : "light_mode";
// Function to create message elements
const createMessageElement = (content, ...classes) => {
    const div = document.createElement("div");
    div.classList.add("message", ...classes);
    div.innerHTML = content;
    return div;
};
// Scroll to the bottom of the container
const scrollToBottom = () => container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
// HTML-escape a string to prevent injection. Markdown links and bare
// URLs are turned into anchors by renderLineContent below.
const escapeHtml = (s) => s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
// Convert ONE line of text into safe HTML: markdown links → anchors,
// bare URLs auto-linked, everything else HTML-escaped. The URL group
// allows one level of balanced parens (some upstream PDF URLs contain
// "(YYYY)"); the backend also percent-encodes parens as defense-in-depth.
const renderLineContent = (text) => {
    const PH = "";                 // private-use sentinel, never in real text
    const links = [];
    let pre = text.replace(
        /\[([^\]]+)\]\((https?:\/\/(?:\([^)]*\)|[^()\s])+)\)/g,
        (_, label, url) => {
            links.push(`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`);
            return PH;
        });
    pre = escapeHtml(pre);
    // Dấu sao đóng của phần in nghiêng hay dính vào đuôi URL trần, nên tách nó
    // ra trước khi dựng thẻ; để dính thì nó thành một phần của đường dẫn.
    pre = pre.replace(/(https?:\/\/[^\s<]+)/g, (m) => {
        const duoi = m.match(/[*_]+$/);
        const url = duoi ? m.slice(0, -duoi[0].length) : m;
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>${duoi ? duoi[0] : ""}`;
    });
    // Trợ lý viết bằng markdown, nên phần đậm và phần tiêu đề phải thành thẻ HTML;
    // để nguyên thì người đọc thấy dấu sao và dấu thăng nằm giữa câu.
    pre = pre.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    pre = pre.replace(/(?<![\w*])\*([^*\n]+)\*(?![\w*])/g, "<em>$1</em>");
    let i = 0;
    return pre.replace(new RegExp(PH, "g"), () => links[i++]);
};
// Bậc tiêu đề markdown ở đầu dòng, trả về số dấu thăng đã cắt.
const headingLevel = (line) => (line.match(/^(#{1,6})\s+/) || ["", ""])[1].length;
// Render each plain-text result line. The SPARQL backend no longer emits a tree.
const renderRichText = (text) => {
    let html = "";
    for (const raw of text.split("\n")) {
        if (/^\s*-{3,}\s*$/.test(raw)) { html += "<hr>"; continue; }
        const content = raw.replace(/\s+$/, "");
        if (!content) { html += '<div class="reply-line spacer"></div>'; continue; }
        const level = headingLevel(content);
        if (level) {
            const body = renderLineContent(content.replace(/^#{1,6}\s+/, ""));
            html += `<div class="reply-line"><strong>${body}</strong></div>`;
            continue;
        }
        // Dòng gạch đầu dòng của markdown. Không bóc dấu dẫn thì người đọc thấy
        // dấu sao nằm chình ình đầu mỗi ý, đúng thứ markdown sinh ra để giấu đi.
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
// Render the bot reply immediately as rich HTML - no typing
// animation. The chatbot is fast enough that incremental reveal
// becomes a delay rather than a delight.
const renderReply = (text, textElement, botMsgDiv) => {
    textElement.innerHTML = renderRichText(text);
    botMsgDiv.classList.remove("loading");
    document.body.classList.remove("bot-responding");
    scrollToBottom();
};
// Đọc luồng sự kiện từ /chat và hiện dần câu trả lời.
//
// Một lượt trả lời gồm nhiều chặng: trợ lý có thể tra cứu vài lần trước khi
// viết. Hiện từng chặng ngay khi tới thì người dùng thấy hệ thống đang làm gì,
// thay vì nhìn màn hình trống suốt quãng đó.
const generateResponse = async (botMsgDiv) => {
    const textElement = botMsgDiv.querySelector(".message-text");
    controller = new AbortController();
    const historyWasTrimmed = chatHistory.length > MAX_HISTORY_MESSAGES;
    const history = chatHistory.slice(-MAX_HISTORY_MESSAGES).map(({ role, text }) => ({
        role: role === "bot" ? "assistant" : "user",
        content: text,
    }));
    chatHistory.push({ role: "user", text: userData.message });
    let answer = "";
    // Thông báo vận hành hiện cùng câu trả lời nhưng không nhập vào `answer`,
    // nên nó không bị gửi lại cho mô hình như một lời nói của trợ lý.
    let notice = historyWasTrimmed
        ? "Cuộc trò chuyện đã dài nên mình chỉ dùng 20 tin nhắn gần nhất; các lượt cũ hơn không còn nằm trong ngữ cảnh."
        : "";
    // Một lượt đi qua ba chặng và chặng nào cũng có thể kéo dài vài giây. Không
    // nói rõ đang ở chặng nào thì mọi quãng chờ trông giống nhau, và giống hệt
    // hệ thống bị treo.
    let status = "Đang suy nghĩ…";
    const paint = () => {
        const noticeHtml = notice
            ? `<div class="reply-line notice">${escapeHtml(notice)}</div>`
            : "";
        textElement.innerHTML = noticeHtml + (answer
            ? renderRichText(answer)
            : `<div class="reply-line status">${escapeHtml(status)}</div>`);
        scrollToBottom();
    };
    paint();
    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userData.message, history }),
            signal: controller.signal,
        });
        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(detail.detail || "Server error");
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const chunks = buffer.split("\n\n");
            buffer = chunks.pop();
            for (const chunk of chunks) {
                const line = chunk.split("\n").find((l) => l.startsWith("data: "));
                if (!line) continue;
                const event = JSON.parse(line.slice(6));
                if (event.loai === "chu") {
                    answer += event.noi_dung;
                    botMsgDiv.classList.remove("loading");
                    paint();
                } else if (event.loai === "tra_cuu") {
                    status = `Đang tra cứu: ${event.tu_khoa}`;
                    paint();
                } else if (event.loai === "tra_cuu_xong") {
                    status = "Đang viết câu trả lời…";
                    paint();
                } else if (event.loai === "hang_doi") {
                    // Đang bận thì phải nói ra. Chờ trong im lặng nhìn không
                    // khác gì hệ thống treo, và người dùng sẽ bấm lại - mà lần
                    // bấm đó lại chiếm thêm một chỗ trong hàng.
                    status = `Hệ thống đang bận, bạn đứng thứ ${event.vi_tri} trong hàng chờ…`;
                    paint();
                } else if (event.loai === "canh_bao") {
                    notice = event.noi_dung;
                    paint();
                } else if (event.loai === "xong") {
                    if (!answer) answer = event.noi_dung;
                    paint();
                } else if (event.loai === "loi") {
                    throw new Error(event.noi_dung);
                }
            }
        }
        botMsgDiv.classList.remove("loading");
        document.body.classList.remove("bot-responding");
        scrollToBottom();
        chatHistory.push({ role: "bot", text: answer });
    } catch (error) {
        textElement.textContent = error.name === "AbortError" ? "Đã dừng phản hồi." : error.message;
        textElement.style.color = "#d62939";
        botMsgDiv.classList.remove("loading");
        document.body.classList.remove("bot-responding");
        scrollToBottom();
    }
};
// Handle the form submission
const handleFormSubmit = (e) => {
    e.preventDefault();
    const userMessage = promptInput.value.trim();
    if (!userMessage || document.body.classList.contains("bot-responding")) return;
    // Bấm gửi lúc máy chủ chưa dậy thì hỏi lại ngay thay vì im lặng không làm
    // gì: người dùng vừa ra tín hiệu là họ đang chờ, nên đừng bắt họ đợi hết
    // quãng giãn cách của lần thử kế tiếp.
    if (!document.body.classList.contains("server-ready")) {
        checkServer();
        return;
    }
    userData.message = userMessage;
    promptInput.value = "";
    document.body.classList.add("chats-active", "bot-responding");
    const userMsgDiv = createMessageElement(`<p class="message-text"></p>`, "user-message");
    userMsgDiv.querySelector(".message-text").textContent = userData.message;
    chatsContainer.appendChild(userMsgDiv);
    scrollToBottom();
    setTimeout(() => {
        const botMsgHTML = `<span class="avatar material-symbols-rounded" style="display:flex;align-items:center;justify-content:center;color:#1d7efd;">school</span> <div class="message-text">Đang tra cứu...</div>`;
        const botMsgDiv = createMessageElement(botMsgHTML, "bot-message", "loading");
        chatsContainer.appendChild(botMsgDiv);
        scrollToBottom();
        generateResponse(botMsgDiv);
    }, 600);
};
// Stop Bot Response
document.querySelector("#stop-response-btn").addEventListener("click", () => {
    controller?.abort();
    chatsContainer.querySelector(".bot-message.loading")?.classList.remove("loading");
    document.body.classList.remove("bot-responding");
});
// Toggle dark/light theme
themeToggleBtn.addEventListener("click", () => {
    const isLightTheme = document.body.classList.toggle("light-theme");
    localStorage.setItem("themeColor", isLightTheme ? "light_mode" : "dark_mode");
    themeToggleBtn.textContent = isLightTheme ? "dark_mode" : "light_mode";
});
// Delete all chats
// Bấm một thẻ gợi ý là gửi luôn câu đó, không phải gõ lại.
document.querySelectorAll(".suggestions-item").forEach((item) => {
    item.addEventListener("click", () => {
        if (document.body.classList.contains("bot-responding")) return;
        promptInput.value = item.querySelector(".text").textContent;
        if (!document.body.classList.contains("server-ready")) {
            checkServer();
            return;
        }
        promptForm.dispatchEvent(new Event("submit"));
    });
});

document.querySelector("#delete-chats-btn").addEventListener("click", () => {
    chatHistory.length = 0;
    chatsContainer.innerHTML = "";
    document.body.classList.remove("chats-active", "bot-responding");
});
promptForm.addEventListener("submit", handleFormSubmit);

// --- Trạng thái máy chủ ------------------------------------------------------
// Nền tảng triển khai tắt hẳn container khi không ai dùng, nên mở trang sau một
// quãng rảnh là rơi đúng vào lúc máy chủ đang dậy. Máy chủ chỉ mở cổng SAU khi
// nạp xong mô hình, nên không có trạng thái nửa vời: hỏi được ``/healthz`` nghĩa
// là sẵn sàng thật.
//
// Chính cú hỏi này LÀ cú đánh thức. Mở trang là container bắt đầu dậy, trong lúc
// người dùng còn đang đọc giao diện và gõ câu hỏi - tới lúc bấm gửi thì phần lớn
// trường hợp đã ấm sẵn, thay vì bắt họ chờ sau khi bấm.
const serverStatus = document.querySelector(".server-status");
// Giãn dần rồi giữ ở tám giây. Một lần hỏng chưa nói lên gì: lúc container đang
// dậy, nền tảng có thể cắt chính cú hỏi này nếu nó lâu hơn hạn của nền tảng.
const HEALTH_WAITS_MS = [1000, 2000, 4000, 8000];
// Hai mươi lần, tức khoảng hai phút - đủ cho một lần cấp máy và kéo ảnh về.
const HEALTH_MAX_ATTEMPTS = 20;

const setServerState = (state, label) => {
    serverStatus.dataset.state = state;
    serverStatus.querySelector(".label").textContent = label;
    document.body.classList.toggle("server-ready", state === "ready");
};

let healthCheckRunning = false;

const checkServer = async () => {
    // Một vòng hỏi tại một thời điểm. Bấm gửi nhiều lần lúc đang chờ mà mỗi lần
    // mở một vòng riêng thì các vòng ghi đè trạng thái của nhau.
    if (healthCheckRunning) return;
    healthCheckRunning = true;
    try {
        for (let attempt = 0; attempt < HEALTH_MAX_ATTEMPTS; attempt++) {
            try {
                const response = await fetch("/healthz", { cache: "no-store" });
                if (response.ok) {
                    setServerState("ready", "Máy chủ sẵn sàng");
                    return;
                }
            } catch (error) {
                // Container đang dậy thì kết nối hỏng hẳn chứ không trả về mã
                // lỗi, nên hai trường hợp đó dẫn tới cùng một chỗ.
            }
            setServerState("waking", "Đang khởi động máy chủ, bạn chờ một chút…");
            const wait = HEALTH_WAITS_MS[Math.min(attempt, HEALTH_WAITS_MS.length - 1)];
            await new Promise((resolve) => setTimeout(resolve, wait));
        }
        setServerState("down", "Chưa kết nối được máy chủ. Bạn thử tải lại trang.");
    } finally {
        healthCheckRunning = false;
    }
};

checkServer();

// Container có thể đã tụt về không trong lúc tab nằm im, nên phải hỏi lại khi
// người dùng quay lại: chấm xanh từ nửa tiếng trước không còn nói lên điều gì.
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    if (document.body.classList.contains("bot-responding")) return;
    checkServer();
});
