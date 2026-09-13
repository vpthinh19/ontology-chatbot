import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

const page = (name) => fileURLToPath(new URL(name, import.meta.url));

export default defineConfig(({ mode }) => {
  const backendToken = loadEnv(mode, process.cwd(), "").BACKEND_API_TOKEN?.trim();

  return {
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
