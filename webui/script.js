const container = document.querySelector(".container");
const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = promptForm.querySelector(".prompt-input");
const themeToggleBtn = document.querySelector("#theme-toggle-btn");
// API Setup — local FastAPI backend
const API_URL = "/chat";
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
    pre = pre.replace(/(https?:\/\/[^\s<]+)/g,
        (m) => `<a href="${m}" target="_blank" rel="noopener noreferrer">${m}</a>`);
    let i = 0;
    return pre.replace(new RegExp(PH, "g"), () => links[i++]);
};
// Convert the bot reply into an indented tree. render.py emits 3 spaces
// per nesting level; here each line becomes a block whose left padding =
// its depth, so a long line that wraps stays aligned (hanging indent).
// Depth-0 lines are titles. A blank line becomes a small vertical gap.
const INDENT_UNIT = 3;
const renderRichText = (text) => {
    let html = "";
    for (const raw of text.split("\n")) {
        if (/^\s*-{3,}\s*$/.test(raw)) { html += "<hr>"; continue; }
        const m = raw.match(/^( *)(.*)$/);
        const depth = Math.floor(m[1].length / INDENT_UNIT);
        const content = m[2].replace(/\s+$/, "");
        if (!content) { html += '<div class="reply-line spacer"></div>'; continue; }
        const cls = depth === 0 ? "reply-line reply-head" : "reply-line";
        html += `<div class="${cls}" style="--depth:${depth}">${renderLineContent(content)}</div>`;
    }
    return html;
};
// Render the bot reply immediately as rich HTML — no typing
// animation. The chatbot is fast enough that incremental reveal
// becomes a delay rather than a delight.
const renderReply = (text, textElement, botMsgDiv) => {
    textElement.innerHTML = renderRichText(text);
    botMsgDiv.classList.remove("loading");
    document.body.classList.remove("bot-responding");
    scrollToBottom();
};
// Call the local FastAPI /chat endpoint and stream the reply.
const generateResponse = async (botMsgDiv) => {
    const textElement = botMsgDiv.querySelector(".message-text");
    controller = new AbortController();
    chatHistory.push({ role: "user", text: userData.message });
    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userData.message }),
            signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Server error");
        const responseText = (data.reply || "").trim();
        renderReply(responseText, textElement, botMsgDiv);
        chatHistory.push({ role: "bot", text: responseText });
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
document.querySelector("#delete-chats-btn").addEventListener("click", () => {
    chatHistory.length = 0;
    chatsContainer.innerHTML = "";
    document.body.classList.remove("chats-active", "bot-responding");
});
promptForm.addEventListener("submit", handleFormSubmit);