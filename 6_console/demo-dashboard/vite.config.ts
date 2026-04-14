import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/metrics': {
        target: 'http://localhost:18011',
        changeOrigin: true,
      },
      '/usage': {
        target: 'http://localhost:18011',
        changeOrigin: true,
      },
      '/debug': {
        target: 'http://localhost:18011',
        changeOrigin: true,
      },
      '/agents': {
        target: 'http://localhost:18011',
        changeOrigin: true,
      },
    },
  },
})
