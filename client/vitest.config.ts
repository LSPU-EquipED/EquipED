// Vitest configuration. We keep the test runner minimal: the helpers
// under test are pure TypeScript, and the PDF generation code is
// exercised via mocked fetch / jsPDF stubs, so no DOM environment
// (jsdom / happy-dom) is required.
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
    globals: false,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
