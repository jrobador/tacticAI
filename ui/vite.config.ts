import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

const API = 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    proxy: {
      '/catalog': API,
      '/recipes': API,
      '/scenario': API,
      '/jobs': API,
      '/matches': API,
      '/library': API,
      '/ws': { target: API, ws: true },
    },
  },
})
