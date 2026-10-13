import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    holdUntilCrawlEnd: false,
  },
  server: {
    port: 3000,
    host: true,
    watch: {
      // OneDrive no manda eventos de FS; sin polling Vite sirve JS viejo.
      usePolling: true,
      interval: 800,
      ignored: ['**/node_modules/**', '**/.git/**'],
    },
  },
});
