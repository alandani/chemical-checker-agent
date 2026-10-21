import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Ketcher expects a few Node built-ins; point them at their browser packages.
  define: { "process.env": {}, global: "globalThis" },
  resolve: {
    alias: { events: "events/", assert: "assert/" },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  build: {
    chunkSizeWarningLimit: 30000, // the structure editor is large; it's lazy-loaded on "Draw"
  },
});
