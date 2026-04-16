import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  test: {
    globals: false, // Don't use globals to avoid conflicts with Playwright
    environment: 'node',
    include: ['tests/unit/**/*.test.ts'], // Only unit tests, not e2e
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/lib/**/*.ts'],
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
});
