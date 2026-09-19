import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

const page = (name) => fileURLToPath(new URL(name, import.meta.url));

// Vercel đổi /admin thành /admin.html (vercel.json); máy chủ của Vite làm giống vậy.
const adminPath = () => {
  const rewrite = (req, _res, next) => {
    if (req.url === "/admin" || req.url.startsWith("/admin?")) req.url = req.url.replace("/admin", "/admin.html");
    next();
  };
  return {
    name: "admin-path",
    // Thân hàm dạng khối: trả về một hàm thì Vite hiểu là hook chạy sau.
    configureServer(server) {
      server.middlewares.use(rewrite);
    },
    configurePreviewServer(server) {
      server.middlewares.use(rewrite);
    },
  };
};

export default defineConfig(({ mode }) => {
  const backendToken = loadEnv(mode, process.cwd(), "").BACKEND_API_TOKEN?.trim();

  return {
    plugins: [adminPath()],
    build: {
      rollupOptions: {
        input: { main: page("./index.html"), admin: page("./admin.html") },
      },
    },
    server: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
          headers: backendToken
            ? { Authorization: `Bearer ${backendToken}` }
            : undefined,
          rewrite: (path) =>
            path === "/api/healthz" ? "/health" : path.replace(/^\/api/, ""),
        },
      },
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
    },
  };
});
