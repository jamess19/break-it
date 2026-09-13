import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Backend chạy riêng (uvicorn app.main:app, port 8000) — proxy để gọi
    // /chat, /plan, /health thẳng bằng relative path, khỏi lo CORS lúc dev.
    proxy: {
      '/chat': 'http://localhost:8000',
      '/plan': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
