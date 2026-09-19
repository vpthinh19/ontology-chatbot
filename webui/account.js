// Ô tài khoản dùng chung cho trang hỏi đáp và trang quản trị. Chỉ có hai tài khoản: khách (mặc định,
// không cần đăng nhập) và quản trị (mật khẩu quản trị). Đăng nhập là phiên cookie sẵn có của máy chủ
// (/api/admin/login, /session, /logout); trang không giữ mật khẩu hay khoá nào.

const ICONS = {
  guest:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>',
  admin:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>',
};

const call = async (path, method = "GET", body) => {
  const response = await fetch(`/api/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, detail: data.detail };
};

// ``other``: nút sang trang kia khi đã là quản trị. ``onChange(role)`` báo mỗi lần đổi tài khoản.
// ``openWhenGuest``: mở sẵn ô mật khẩu cho khách (trang quản trị không có gì cho khách xem).
export const mountAccount = (root, { other, onChange = () => {}, openWhenGuest = false }) => {
  root.classList.add("account");
  root.innerHTML = `
    <span class="account-icon" role="img"></span>
    <button type="button" id="account-login" class="account-button">Đăng nhập</button>
    <a id="account-switch" class="account-button" href="${other.href}">${other.label}</a>
    <button type="button" id="account-logout" class="account-button">Đăng xuất</button>
    <form id="account-form" class="account-form" hidden>
      <label class="sr-only" for="account-password">Mật khẩu quản trị</label>
      <input id="account-password" type="password" placeholder="Mật khẩu quản trị" autocomplete="current-password" required />
      <button type="submit" class="account-button primary">Vào</button>
      <p id="account-error" class="account-error" role="alert" hidden></p>
    </form>`;
  const $ = (selector) => root.querySelector(selector);
  const form = $("#account-form");
  const error = $("#account-error");
  let role = null;

  const showError = (text) => {
    error.textContent = text;
    error.hidden = !text;
  };
  const openForm = (open) => {
    form.hidden = !open;
    showError("");
    if (open) $("#account-password").focus();
  };
  const setRole = (next) => {
    const changed = next !== role;
    role = next;
    root.dataset.role = next;
    const icon = $(".account-icon");
    icon.innerHTML = ICONS[next];
    icon.setAttribute("aria-label", next === "admin" ? "Tài khoản: quản trị" : "Tài khoản: khách");
    icon.title = next === "admin" ? "Quản trị" : "Khách";
    $("#account-login").hidden = next === "admin";
    $("#account-switch").hidden = next !== "admin";
    $("#account-logout").hidden = next !== "admin";
    openForm(next === "guest" && openWhenGuest);
    if (changed) onChange(next);
  };

  $("#account-login").addEventListener("click", () => openForm(form.hidden));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = $("#account-password");
    try {
      const result = await call("/login", "POST", { key: password.value });
      if (!result.ok) {
        showError(result.detail || `Máy chủ trả lỗi ${result.status}.`);
        password.select();
        return;
      }
    } catch {
      showError("Chưa kết nối được máy chủ. Bạn thử lại sau.");
      return;
    }
    password.value = "";
    setRole("admin");
  });
  $("#account-logout").addEventListener("click", async () => {
    await call("/logout", "POST").catch(() => {});
    setRole("guest");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !form.hidden && !openWhenGuest) openForm(false);
  });

  const ready = call("/session")
    .then((result) => setRole(result.ok ? "admin" : "guest"))
    .catch(() => setRole("guest"));

  // Phiên hết hạn giữa chừng (máy chủ trả 401): quay về khách.
  return { ready, signedOut: () => setRole("guest") };
};
