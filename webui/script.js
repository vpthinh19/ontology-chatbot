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
// Convert plain text with markdown-style links and newlines into safe
// HTML. URLs in the form [label](url) become anchor tags; bare http(s)
// URLs are auto-linked; everything else is HTML-escaped to prevent
// injection.
const escapeHtml = (s) => s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const renderRichText = (text) => {
    const PLACEHOLDER = "LINK";
    const links = [];
    // 1) extract markdown links so their inner HTML survives escaping.
    //    The URL group allows one level of balanced parens — needed
    //    because some upstream PDF URLs contain literal "(YYYY)" or
    //    "(N)" segments. Backend also percent-encodes parens; this
    //    regex is defense-in-depth against any URL that slips through
    //    without encoding.
    let pre = text.replace(
        /\[([^\]]+)\]\((https?:\/\/(?:\([^)]*\)|[^()\s])+)\)/g,
        (_, label, url) => {
            links.push(`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`);
            return PLACEHOLDER;
        });
    // 2) escape the rest
    pre = escapeHtml(pre);
    // 3) auto-link bare URLs (post-escape so the http// chars survived)
    pre = pre.replace(/(https?:\/\/[^\s<]+)/g,
        (m) => `<a href="${m}" target="_blank" rel="noopener noreferrer">${m}</a>`);
    // 4) restore markdown links
    let i = 0;
    pre = pre.replace(new RegExp(PLACEHOLDER, "g"), () => links[i++]);
    // 5) newlines → <br>
    return pre.replace(/\n/g, "<br>");
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
        const botMsgHTML = `<span class="avatar material-symbols-rounded" style="display:flex;align-items:center;justify-content:center;color:#1d7efd;">school</span> <p class="message-text">Đang tra cứu...</p>`;
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