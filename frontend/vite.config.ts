import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Web beta: bind to LAN so phones on the same Wi-Fi can open the link.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    host: true,
    port: 4173,
  },
})
