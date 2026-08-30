import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api/8004scan": {
        target: "https://api.8004scan.io",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/8004scan/, "/api/v1"),
      },
      "/api/missions": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
