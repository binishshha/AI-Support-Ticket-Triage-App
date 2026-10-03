import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          // Local dev: your FastAPI server. Override with VITE_API_URL if needed.
          target: env.VITE_API_URL || "http://localhost:8000",
          changeOrigin: true,
          secure: true,
        },
      },
    },
  };
});
