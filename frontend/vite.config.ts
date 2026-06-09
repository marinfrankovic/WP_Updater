import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server runs on 5174 so it does not collide with other local apps
// (bank-statement-analyzer uses 5173). In dev, /api is proxied to the Flask
// backend (default 127.0.0.1:8090). The production build is emitted into
// ../app/webui so the Flask container can serve the SPA + API from one origin.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: '../app/webui',
    emptyOutDir: true,
  },
  server: {
    port: 5174,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5174,
    host: '127.0.0.1',
  },
});
