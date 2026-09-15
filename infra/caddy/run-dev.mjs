#!/usr/bin/env node
import { spawn } from 'node:child_process';

const check = spawn('caddy', ['version']);

check.on('error', () => {
  console.log('\x1b[33m[caddy] Caddy binary not found in PATH.\x1b[0m');
  console.log('\x1b[36m[caddy] Falling back to Faculty Vite proxy on http://localhost:5173\x1b[0m');
  console.log('[caddy] Faculty, Admin, and API proxying are available at http://localhost:5173');
  // Keep process alive so concurrently doesn't kill other services
  const timer = setInterval(() => {}, 1000 * 60 * 60);
  process.on('SIGINT', () => {
    clearInterval(timer);
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    clearInterval(timer);
    process.exit(0);
  });
});

check.on('close', (code) => {
  if (code === 0) {
    const caddy = spawn(
      'caddy',
      ['run', '--config', 'infra/caddy/Caddyfile.dev', '--adapter', 'caddyfile'],
      { stdio: 'inherit' }
    );
    caddy.on('exit', (exitCode) => process.exit(exitCode ?? 0));
    process.on('SIGINT', () => caddy.kill('SIGINT'));
    process.on('SIGTERM', () => caddy.kill('SIGTERM'));
  }
});
