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

const buildVersion = process.env.VITE_APP_VERSION || String(Date.now());

function generateVersionJsonPlugin() {
  return {
    name: 'generate-version-json',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'version.json',
        source: JSON.stringify({
          version: buildVersion,
          buildTime: new Date().toISOString(),
        }, null, 2),
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    generateVersionJsonPlugin(),
  ],
  define: {
    __APP_BUILD_VERSION__: JSON.stringify(buildVersion),
  },
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
