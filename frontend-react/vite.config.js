import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

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
    port: 9090, host: true, // Keeping the same frontend port the user is used to
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/formats': 'http://127.0.0.1:8000',
      '/metadata': 'http://127.0.0.1:8000',
      '/download': 'http://127.0.0.1:8000',
      '/download-thumbnail': 'http://127.0.0.1:8000',
      '/automate': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
