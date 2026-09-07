import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 30000,
  use: {
    baseURL: process.env.WORKBENCH_URL || "http://127.0.0.1:8000",
    browserName: "chromium",
    viewport: { width: 1440, height: 1050 },
    screenshot: "only-on-failure",
  },
});
