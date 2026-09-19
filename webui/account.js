// Ô tài khoản ở góc phải, dùng chung cho trang hỏi đáp và trang quản trị. Chỉ hiện một avatar; bấm vào
// mới mở hộp nhỏ: tên tài khoản (khách hoặc quản trị) và các nút. Đăng nhập là gửi KEY tới
// /api/admin/login để nhận cookie phiên của máy chủ; trang không giữ KEY.

const ICONS = {
  guest:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>',
  admin:
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>',
};
const NAMES = { guest: "Tài khoản: khách", admin: "Tài khoản: quản trị" };

const call = async (path, method = "GET", body) => {
  const response = await fetch(`/api/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, detail: data.detail };
};

class AccountMenu {
  // ``other``: đường sang trang kia khi đã là quản trị. ``onChange(role)`` chạy mỗi lần đổi tài khoản.
  // ``openWhenGuest``: khách vào trang này thì mở sẵn ô KEY (trang quản trị không có gì cho khách xem).
  constructor(root, { other, onChange = () => {}, openWhenGuest = false }) {
    root.classList.add("account");
    root.innerHTML = `
      <button type="button" id="account-toggle" class="account-icon" aria-haspopup="dialog" aria-expanded="false"
        aria-controls="account-panel"></button>
      <div id="account-panel" class="account-panel" role="dialog" aria-labelledby="account-name" hidden>
        <p id="account-name" class="account-name"></p>
        <div class="account-actions">
          <button type="button" id="account-login" class="account-button">Đăng nhập</button>
          <a id="account-switch" class="account-button" href="${other.href}">${other.label}</a>
          <button type="button" id="account-logout" class="account-button">Đăng xuất</button>
        </div>
        <form id="account-form" class="account-form" hidden>
          <label class="sr-only" for="account-password">KEY</label>
          <input id="account-password" type="password" placeholder="KEY" autocomplete="current-password" required />
          <button type="submit" class="account-button primary">Vào</button>
          <p id="account-error" class="account-error" role="alert" hidden></p>
        </form>
      </div>`;
    this.root = root;
    this.onChange = onChange;
    this.openWhenGuest = openWhenGuest;
    this.role = null;
    const $ = (selector) => root.querySelector(selector);
    this.toggle = $("#account-toggle");
    this.panel = $("#account-panel");
    this.name = $("#account-name");
    this.login = $("#account-login");
    this.switchLink = $("#account-switch");
    this.logout = $("#account-logout");
    this.form = $("#account-form");
    this.key = $("#account-password");
    this.error = $("#account-error");

    this.toggle.addEventListener("click", () => this.open(this.panel.hidden));
    this.login.addEventListener("click", () => this.showForm(true));
    this.form.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.signIn();
    });
    this.logout.addEventListener("click", async () => {
      await call("/logout", "POST").catch(() => {});
      this.setRole("guest");
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !this.panel.hidden && !this.sticky) {
        this.open(false);
        this.toggle.focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!this.panel.hidden && !this.sticky && !root.contains(event.target)) this.open(false);
    });

    this.ready = call("/session")
      .then((result) => this.setRole(result.ok ? "admin" : "guest"))
      .catch(() => this.setRole("guest"));
  }

  // Khách ở trang quản trị: hộp luôn mở, vì trang không còn gì khác để làm.
  get sticky() {
    return this.openWhenGuest && this.role === "guest";
  }

  open(open) {
    this.panel.hidden = !open;
    this.toggle.setAttribute("aria-expanded", String(open));
    if (!open) this.showForm(false);
  }

  showForm(show) {
    this.form.hidden = !show;
    this.login.hidden = show || this.role === "admin";
    this.showError("");
    if (show) this.key.focus();
  }

  showError(text) {
    this.error.textContent = text;
    this.error.hidden = !text;
  }

  async signIn() {
    try {
      const result = await call("/login", "POST", { key: this.key.value });
      if (!result.ok) {
        this.showError(result.detail || `Máy chủ trả lỗi ${result.status}.`);
        this.key.select();
        return;
      }
    } catch {
      this.showError("Chưa kết nối được máy chủ. Bạn thử lại sau.");
      return;
    }
    this.key.value = "";
    this.setRole("admin");
  }

  setRole(role) {
    const changed = role !== this.role;
    this.role = role;
    this.root.dataset.role = role;
    this.toggle.innerHTML = ICONS[role];
    this.toggle.setAttribute("aria-label", NAMES[role]);
    this.toggle.title = NAMES[role];
    this.name.textContent = NAMES[role];
    this.switchLink.hidden = role !== "admin";
    this.logout.hidden = role !== "admin";
    this.open(this.sticky);
    if (this.sticky) this.showForm(true);
    if (changed) this.onChange(role);
  }

  // Phiên hết hạn giữa chừng (máy chủ trả 401): về tài khoản khách.
  signedOut() {
    this.setRole("guest");
  }
}

export const mountAccount = (root, options) => new AccountMenu(root, options);
