/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Fail loudly if 5173 is taken instead of silently drifting to another
    // port -- the backend's OAuth redirect and CORS origin are both pinned to
    // this port (FRONTEND_URL in .env), so a silent port drift here breaks
    // login in a confusing way (see docs/build_log.md).
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
