import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Web beta: bind for same-Wi‑Fi / LAN access only (e.g. phone → http://<lan-ip>:5173).
// Do not use public tunneling clients on corp devices.
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
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
