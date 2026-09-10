import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
const djangoProxy = {
  target: proxyTarget,
  changeOrigin: false,
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: 'src/test/setupTests.ts',
    css: true,
  },
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': djangoProxy,
      '/admin': djangoProxy,
      '/static': djangoProxy,
      '/media': djangoProxy,
    },
  },
})
