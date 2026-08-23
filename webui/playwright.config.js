import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  timeout: 15_000,
  use: {
    browserName: "chromium",
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run build && npm run preview",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      VITE_API_BASE_URL: "https://lightning.example.test",
      VITE_API_KEY: "test-api-key",
    },
  },
});
