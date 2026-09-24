import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The API is served by the agent's FastAPI app, so proxying here keeps
      // the browser on one origin and avoids CORS entirely in development.
      '/candidate': 'http://127.0.0.1:8000',
      '/interview': 'http://127.0.0.1:8000',
    },
  },
})
