import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

/**
 * Vite config for UI components (popup, pages).
 * These are loaded via HTML with type="module" so ES modules work fine.
 *
 * Background/content/inject scripts are built separately via vite.config.scripts.ts
 * because Firefox MV2 loads them as classic scripts (not ES modules).
 */
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: '',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: mode === 'development',
    minify: mode === 'production',
    rollupOptions: {
      input: {
        popup: resolve(__dirname, 'src/popup/index.html'),
        'ip-warning': resolve(__dirname, 'src/pages/ip-warning.html'),
        onboarding: resolve(__dirname, 'src/pages/onboarding.html'),
        options: resolve(__dirname, 'src/pages/options.html'),
        'test-runner': resolve(__dirname, 'src/pages/test-runner.html'),
      },
      output: {
        format: 'es',
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === 'popup') return 'popup/index.js';
          if (chunkInfo.name === 'ip-warning') return 'pages/ip-warning.js';
          if (chunkInfo.name === 'onboarding') return 'pages/onboarding.js';
          if (chunkInfo.name === 'options') return 'pages/options.js';
          return '[name].js';
        },
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
        manualChunks(id) {
          // Create chunk for React (shared by all UI components)
          if (id.includes('node_modules/react')) {
            return 'jsx-runtime';
          }
          return undefined;
        },
      },
      treeshake: {
        moduleSideEffects: true,
      },
    },
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify(mode || 'development'),
  },
}));
