// Trạng thái máy chủ ở chân trang. Dịch vụ có thể đang ngủ (không còn bản nào chạy), nên trang hỏi
// /healthz với khoảng chờ giãn dần tới khi máy chủ trả lời hoặc hết ba phút.

export const apiUrl = (path) => `/api${path}`;
// Khoá dịch vụ sai: hỏi lại bao nhiêu lần cũng vẫn sai, nên dừng ngay thay vì chờ hết hạn.
export const isRejectedKey = (status) => status === 401 || status === 403;

export const LABELS = {
  waking: "Đang kết nối máy chủ",
  ready: "Máy chủ sẵn sàng",
  offline: "Thiết bị đang mất kết nối mạng.",
  down: "Chưa kết nối được máy chủ. Hãy thử lại sau ít phút.",
  blocked: "Máy chủ từ chối xác thực dịch vụ của trang này.",
};

const DEADLINE_MS = 180_000;
const REQUEST_TIMEOUT_MS = 12_000;
const WAITS_MS = [1_000, 2_000, 4_000, 8_000];
const COUNTDOWN_SECONDS = 5;

const sleep = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export class ServerStatus {
  // ``element``: khối .server-status gồm .dot, .label, .connection-countdown. ``onChange(state)`` chạy
  // sau mỗi lần đổi trạng thái.
  constructor(element, { onChange = () => {} } = {}) {
    this.element = element;
    this.label = element.querySelector(".label");
    this.countdown = element.querySelector(".connection-countdown");
    this.onChange = onChange;
    this.state = undefined;
    this.lastReadyAt = 0;
    this.pending = undefined;
    this.timer = undefined;
  }

  get ready() {
    return this.state === "ready";
  }

  set(state, label = LABELS[state]) {
    const previous = this.state;
    this.state = state;
    // Không ghi lại đúng nội dung cũ: vùng role=status sẽ đọc lặp lại cho trình đọc màn hình.
    if (this.element.dataset.state !== state || this.label.textContent !== label) {
      this.element.dataset.state = state;
      this.label.textContent = label;
    }
    // Sẵn sàng chỉ hiện chấm xanh; chữ vẫn còn cho trình đọc màn hình và khi rê chuột.
    this.label.classList.toggle("sr-only", state === "ready");
    this.element.title = state === "ready" ? label : "";
    if (state === "waking" && previous !== "waking") this.startCountdown();
    else if (state !== "waking") this.stopCountdown();
    if (state === "ready") this.lastReadyAt = Date.now();
    this.onChange(state);
  }

  // Một vòng kiểm tại một thời điểm; gọi lúc đang kiểm thì nhận lại chính vòng đó.
  check() {
    this.pending ??= this.wake().finally(() => {
      this.pending = undefined;
    });
    return this.pending;
  }

  async wake() {
    if (!navigator.onLine) return this.stop("offline");
    // Trạng thái sẵn sàng cũ không bảo đảm máy chủ còn chạy: đóng nút gửi tới khi có câu trả lời mới.
    this.set("waking");
    const deadline = Date.now() + DEADLINE_MS;
    for (let attempt = 0; Date.now() < deadline; attempt += 1) {
      const outcome = await this.probe();
      // Mạng có thể mất trong lúc chờ: kết quả cũ không được đè lên trạng thái mất mạng.
      if (!navigator.onLine) return this.stop("offline");
      if (outcome === "ready") {
        this.set("ready");
        return true;
      }
      if (outcome === "blocked") return this.stop("blocked");
      this.set("waking");
      const wait = WAITS_MS[Math.min(attempt, WAITS_MS.length - 1)];
      await sleep(wait + Math.round(wait * Math.random() * 0.15));
      if (!navigator.onLine) return this.stop("offline");
    }
    return this.stop("down");
  }

  stop(state) {
    this.set(state);
    return false;
  }

  async probe() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(apiUrl("/healthz"), { cache: "no-store", signal: controller.signal });
      if (response.ok) return "ready";
      return isRejectedKey(response.status) ? "blocked" : "waking";
    } catch {
      return "waking";
    } finally {
      window.clearTimeout(timeout);
    }
  }

  startCountdown() {
    this.stopCountdown();
    let seconds = COUNTDOWN_SECONDS;
    this.countdown.textContent = ` (${seconds})`;
    this.timer = window.setInterval(() => {
      seconds -= 1;
      this.countdown.textContent = seconds >= 0 ? ` (${seconds})` : "…";
      if (seconds < 0) window.clearInterval(this.timer);
    }, 1_000);
  }

  stopCountdown() {
    window.clearInterval(this.timer);
    this.timer = undefined;
    this.countdown.textContent = "";
  }
}
