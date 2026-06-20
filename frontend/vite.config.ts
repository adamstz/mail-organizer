/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Where the backend lives. Defaults to localhost for native (non-Docker) dev;
// docker-compose overrides this to http://backend:8000 since "localhost" inside
// the frontend container would otherwise point at itself, not the backend container.
const backendTarget = process.env.BACKEND_PROXY_TARGET || 'http://localhost:8000';
const backendWsTarget = backendTarget.replace(/^http/, 'ws');

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendWsTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      '/messages': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/labels': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/models': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/filter': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/stats': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
});
