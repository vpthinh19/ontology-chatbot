import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  if (command === "build" && !env.VITE_API_BASE_URL?.trim()) {
    throw new Error(
      "VITE_API_BASE_URL is required for a production build (for example, https://your-lightning-api.example)",
    );
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
