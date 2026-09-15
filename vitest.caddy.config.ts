import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  root: __dirname,
  test: {
    globals: true,
    environment: 'node',
    include: [path.resolve(__dirname, 'infra/caddy/__tests__/**/*.test.ts')],
  },
});
