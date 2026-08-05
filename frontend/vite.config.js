import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Plain host dev (`npm run dev`) reaches the backend at localhost:8000. Inside docker-compose,
// the frontend container instead reaches it at the `api` service's in-network address —
// set via VITE_DEV_API_TARGET there (see docker-compose.yml).
const apiProxyTarget = process.env.VITE_DEV_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
