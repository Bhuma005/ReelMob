import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
