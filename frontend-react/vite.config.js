import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';
const proxyEndpoints = ['/auth', '/formats', '/metadata', '/download', '/download-thumbnail', '/automate', '/api'];
const proxy = proxyEndpoints.reduce((acc, path) => {
  acc[path] = {
    target: proxyTarget,
    changeOrigin: true,
  };
  return acc;
}, {});

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('recharts')) return 'vendor-charts';
            if (id.includes('framer-motion')) return 'vendor-motion';
            if (id.includes('lucide-react')) return 'vendor-icons';
            if (id.includes('react') || id.includes('zustand') || id.includes('@tanstack')) return 'vendor-react';
          }
        }
      }
    }
  },
  server: {
    port: 9090,
    host: true,
    proxy
  }
})
