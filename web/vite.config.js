import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    // En Windows + Docker (bind mount) inotify no propaga eventos de archivo,
    // así que el HMR no detecta cambios. El polling lo soluciona.
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api-proxy': {
        target: 'http://api:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-proxy/, ''),
      },
    },
  },
})
