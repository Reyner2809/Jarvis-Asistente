import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite sirve la UI de React. Electron la carga desde http://localhost:5173 en
// dev, y desde el build estatico (dist/) en produccion.
export default defineConfig({
  plugins: [react()],
  base: './', // rutas relativas para que funcione con file:// en produccion
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
