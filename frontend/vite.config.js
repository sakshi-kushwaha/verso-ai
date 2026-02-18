import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/ws': {
        target: 'http://backend:8000',
        ws: true,
      },
      '/upload': 'http://backend:8000',
      '/uploads': 'http://backend:8000',
      '/audio': 'http://backend:8000',
      '/feed': 'http://backend:8000',
      '/chat': 'http://backend:8000',
      '/flashcards': 'http://backend:8000',
      '/auth': 'http://backend:8000',
      '/onboarding': 'http://backend:8000',
      '/health': 'http://backend:8000',
      '/bg-images': 'http://backend:8000',
    },
  },
})
