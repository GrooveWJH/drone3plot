import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/dashboard': 'http://127.0.0.1:5050',
      '/static': 'http://127.0.0.1:5050',
      '/socket.io': {
        target: 'http://127.0.0.1:5050',
        ws: true,
      },
      '/api': 'http://127.0.0.1:5050',
      '/telemetry': 'http://127.0.0.1:5050',
      '/pose': {
        target: 'http://127.0.0.1:5050',
        ws: true,
      },
      '/media': 'http://127.0.0.1:5050',
    },
  },
})
