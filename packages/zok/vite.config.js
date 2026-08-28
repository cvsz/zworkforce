import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxy = {
  '/api': {
    target: `http://127.0.0.1:${process.env.PORT || 3005}`,
    changeOrigin: true
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5175,
    allowedHosts: ['zok.zeaz.dev'],
    proxy: apiProxy
  },
  preview: {
    host: '127.0.0.1',
    port: Number(process.env.ZOK_PREVIEW_PORT || 5175),
    proxy: apiProxy
  }
})
