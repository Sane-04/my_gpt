// 模块说明：Vite 构建配置，声明 Vue 插件、路径别名和测试环境。
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// Vite 配置：接入 Vue、Tailwind，并提供 @ 到 src 的稳定路径别名。
export default defineConfig({
  // 插件顺序保持简单：Vue 负责单文件组件，Tailwind 负责样式编译。
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      // @ 别名用于业务代码导入，避免多层相对路径影响可读性。
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // Vitest 使用 jsdom 模拟浏览器环境，覆盖 Pinia store 和 localStorage 行为。
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
