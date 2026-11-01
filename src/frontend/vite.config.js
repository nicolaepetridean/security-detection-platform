import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend is expected on :8000. We proxy /api -> backend so the browser talks to
// a single origin in dev and we avoid CORS fiddling.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
