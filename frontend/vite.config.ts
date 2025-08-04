import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

import { maatPlugin } from "./vite-plugin-maat";

// https://vite.dev/config/
export default defineConfig({
  base: "/maat",
  plugins: [react(), tailwindcss(), maatPlugin()],
  build: {
    assetsDir: "_assets",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vm: ["virtual:maat-view-model"],
        },
      },
    },
  },
});
