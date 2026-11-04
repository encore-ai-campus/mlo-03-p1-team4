import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // 백엔드가 생기면 /api 요청을 FastAPI(8000)로 넘긴다. 배포에서는 Nginx가 같은 일을 한다.
    proxy: { '/api': { target: 'http://localhost:8000', rewrite: (path) => path.replace(/^\/api/, '') } },
  },
})
