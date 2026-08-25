import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const backendToken = loadEnv(mode, process.cwd(), "").BACKEND_API_TOKEN?.trim();

  return {
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
