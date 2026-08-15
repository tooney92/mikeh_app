import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Vite refuses requests whose Host header it doesn't recognise, which is
    // exactly what a tunnel sends. Allow the tunnel domains we actually use.
    allowedHosts: ['.trycloudflare.com', '.cfargotunnel.com'],
    // Dev-only: forward /api to the FastAPI service so the browser sees one
    // origin and we never hit CORS locally. In production VITE_API_BASE_URL
    // points at the deployed API instead.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
