import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://es.developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Host
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    strictPort: true,
  },
})