import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend calls /api/...; the dev server forwards that to FastAPI without
// the prefix. One origin means no CORS setup, and the /api prefix keeps API
// paths (/applicant/form) apart from page routes (/applicant).
const API = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
