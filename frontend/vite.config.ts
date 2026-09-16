import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In production, the FastAPI backend serves this app's build output from
// the same origin (see backend/app/main.py), so the frontend never needs to
// know a different host/port and there is no CORS surface at all. The dev
// server proxy below exists purely so `npm run dev` can hot-reload against
// a backend running on its default port while developing.
const BACKEND_DEV_TARGET = "http://127.0.0.1:8420";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: BACKEND_DEV_TARGET, changeOrigin: true },
      "/ws": { target: BACKEND_DEV_TARGET, ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
