import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: `npm run dev` on :5173 proxies /api to the Python server (`mtgcv serve`, :8000).
// Prod: `npm run build` emits web/dist, which `mtgcv serve` serves directly.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
