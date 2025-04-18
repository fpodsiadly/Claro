import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // Bazowa ścieżka dla zasobów
  build: {
    outDir: '../dist', // Katalog wyjściowy
  },
})
