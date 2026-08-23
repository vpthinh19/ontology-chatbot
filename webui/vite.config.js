import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // Bản build thiếu một trong hai biến này thì trang lên được nhưng không gọi
  // nổi backend, và lỗi chỉ lộ ra trong trình duyệt của người dùng. Chặn ngay ở
  // đây để Vercel báo đỏ lúc build thay vì deploy một trang chết.
  if (command === "build") {
    const missing = ["VITE_API_BASE_URL", "VITE_API_KEY"].filter(
      (name) => !env[name]?.trim(),
    );
    if (missing.length) {
      throw new Error(
        `${missing.join(", ")} required for a production build; set them in the Vercel project environment`,
      );
    }
  }

  return {
    server: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
      proxy: {
        "/healthz": "http://127.0.0.1:8000",
        "/chat": "http://127.0.0.1:8000",
      },
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
    },
  };
});
