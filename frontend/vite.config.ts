import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // Load .env.production (or .env) so VITE_BASE_PATH is available at build time
  const env = loadEnv(mode, process.cwd(), '')
  const base = env.VITE_BASE_PATH || '/'

  return {
    plugins: [react()],

    // Base URL — '/' for root, '/meck-bet/' for subpath deployments.
    // Set via frontend/.env.production: VITE_BASE_PATH=/meck-bet/
    base,

    // Production build → frontend/dist/ (served by FastAPI as static files)
    build: {
      outDir: path.resolve(__dirname, 'dist'),
      emptyOutDir: true,
    },

    // Dev server: proxy /api → backend, respects base path
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
