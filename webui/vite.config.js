import { defineConfig } from "vite";

export default defineConfig(() => ({
  server: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
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
}));
