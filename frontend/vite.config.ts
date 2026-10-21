import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Con el store virtual global de pnpm, las dependencias no ven react/react-dom como pares:
  // se resuelven siempre desde el proyecto.
  resolve: { dedupe: ['react', 'react-dom'] },
  build: { chunkSizeWarningLimit: 2000 },
  test: { environment: 'node' },
});
