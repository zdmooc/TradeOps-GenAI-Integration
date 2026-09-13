import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/market": {
        target: "http://localhost:8011",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/market/, ""),
      },
      "/api/workflow": {
        target: "http://localhost:8012",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/workflow/, ""),
      },
      "/api/agent": {
        target: "http://localhost:8015",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/agent/, ""),
      },
    },
  },
});
