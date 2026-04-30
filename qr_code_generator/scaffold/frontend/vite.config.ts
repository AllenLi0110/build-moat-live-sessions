/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
      '/r':   { target: 'http://localhost:8000', changeOrigin: false },
    },
  },
  test: {
    environment: 'node',
  },
})
