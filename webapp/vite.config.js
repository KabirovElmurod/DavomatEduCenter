import { defineConfig } from "vite";

export default defineConfig({
  base: "/webapp/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
    target: "es2020",
    cssCodeSplit: false,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
