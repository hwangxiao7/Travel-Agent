import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Web beta: LAN + public tunnels (Cloudflare / ngrok).
// allowedHosts: true is required so trycloudflare.com Host headers work.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    host: true,
    port: 4173,
    allowedHosts: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
