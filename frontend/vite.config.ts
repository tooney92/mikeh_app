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
      // The server-rendered admin back office sits OUTSIDE /api, so it needs
      // its own proxy entry. Without this the sidebar's Back Office link has
      // to point at the backend's origin directly, which is correct on this
      // machine and dead for anyone reaching the app over a tunnel — only
      // 5173 is exposed there.
      '/admin': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        // NOT changeOrigin, unlike /api. The back office is server-rendered and
        // issues absolute redirects (/admin -> /admin/, and the login flow):
        // rewriting the Host header makes it build those from its OWN origin,
        // so a tunnel visitor gets bounced to 127.0.0.1:8000 and dies there.
        // Passing the original Host through makes it redirect to whatever
        // origin the visitor actually used.
        changeOrigin: false,
        // Belt and braces: rewrite the host of any Location header it still
        // sends absolutely.
        autoRewrite: true,
      },
    },
  },
})
