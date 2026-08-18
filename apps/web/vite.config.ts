import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [vue(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
        // 后端实际接口从 /auth 开始，不包含 /api 前缀。
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // 当前前端默认直接使用 /auth；保留该代理以兼容现有接口调用。
      "/auth": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
});
