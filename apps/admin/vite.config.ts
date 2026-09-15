import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig(({ command }) => ({
  root: __dirname,
  // Keep Vite's development module graph out of the faculty app's /src/*
  // namespace. Production remains rooted at / so deployed routes are unchanged.
  base: '/',
  build: {
    assetsDir: 'admin-assets',
  },
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'admin-spa-route-entry',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url && /^\/(admin|matrix|evaluation-map)(\/|$)/.test(req.url)) {
            req.url = '/';
          }
          next();
        });
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
}));
