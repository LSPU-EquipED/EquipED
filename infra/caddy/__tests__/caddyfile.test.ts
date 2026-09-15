import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

describe('Caddyfile Route Contract', () => {
  const caddyfilePath = path.resolve(__dirname, '../Caddyfile.dev');
  const caddyfileContent = fs.readFileSync(caddyfilePath, 'utf-8');

  it('exists and defines the default dev address :3000 with env override', () => {
    expect(fs.existsSync(caddyfilePath)).toBe(true);
    expect(caddyfileContent).toMatch(/\{\$CADDY_DEV_ADDR::3000\}/);
  });

  it('enforces explicit route block with ordered routing rules', () => {
    // Must contain route block for deterministic top-to-bottom route evaluation in Caddy
    expect(caddyfileContent).toMatch(/route\s*\{/);

    // Locate the positions of the route handlers within the route block
    const apiIndex = caddyfileContent.indexOf('@api');
    const adminIndex = caddyfileContent.indexOf('@admin');
    const facultyFallbackIndex = caddyfileContent.indexOf('handle {');

    expect(apiIndex).toBeGreaterThan(-1);
    expect(adminIndex).toBeGreaterThan(-1);
    expect(facultyFallbackIndex).toBeGreaterThan(-1);

    // Explicit route ordering invariant:
    // 1. /api -> FastAPI
    // 2. /admin /matrix /evaluation-map -> Admin Vite
    // 3. Fallback handle -> Faculty Vite
    expect(apiIndex).toBeLessThan(adminIndex);
    expect(adminIndex).toBeLessThan(facultyFallbackIndex);
  });

  it('matches exact API route matcher pattern without stripping path or falling back to SPA', () => {
    // Must match /api and /api/*
    expect(caddyfileContent).toMatch(/@api\s+path\s+\/api\s+\/api\/\*/);
    // Reverse proxy to FastAPI server on 8000 with SERVER_UPSTREAM override
    expect(caddyfileContent).toMatch(/reverse_proxy\s+\{\$SERVER_UPSTREAM:127\.0\.0\.1:8000\}/);
    // Must not rewrite or strip paths
    expect(caddyfileContent).not.toMatch(/uri\s+strip_prefix/);
  });

  it('matches exact Admin route matchers including admin-assets, bare paths, and descendants', () => {
    const adminPattern =
      /@admin\s+path\s+\/admin-dev\/\*\s+\/admin-assets\/\*\s+\/admin\s+\/admin\/\*\s+\/matrix\s+\/matrix\/\*\s+\/evaluation-map\s+\/evaluation-map\/\*/;
    expect(caddyfileContent).toMatch(adminPattern);
    // Reverse proxy to Admin Vite server on 5174 with ADMIN_UPSTREAM override
    expect(caddyfileContent).toMatch(/reverse_proxy\s+\{\$ADMIN_UPSTREAM:127\.0\.0\.1:5174\}/);
  });

  it('falls back to Faculty Vite server for all remaining routes', () => {
    expect(caddyfileContent).toMatch(/reverse_proxy\s+\{\$FACULTY_UPSTREAM:127\.0\.0\.1:5173\}/);
  });

  it('runs caddy adapt syntax validation when caddy binary is available', () => {
    let caddyAvailable = false;
    try {
      execSync('which caddy', { stdio: 'pipe' });
      caddyAvailable = true;
    } catch {
      caddyAvailable = false;
    }

    if (!caddyAvailable) {
      console.info(
        '[Caddyfile Contract Test] caddy binary not found in PATH; parser adapt test skipped honestly (static contract verified).'
      );
      expect(caddyAvailable).toBe(false);
      return;
    }

    // When caddy is installed in environment, run caddy validate / adapt
    const output = execSync(
      `caddy adapt --config "${caddyfilePath}" --adapter caddyfile`,
      { encoding: 'utf-8' }
    );
    expect(output).toBeDefined();
    const parsed = JSON.parse(output);
    expect(parsed).toHaveProperty('apps');
  });
});

describe('Caddyfile.prod Route Contract', () => {
  const caddyfilePath = path.resolve(__dirname, '../Caddyfile.prod');
  const caddyfileContent = fs.readFileSync(caddyfilePath, 'utf-8');

  it('exists and defines the default address :{$PORT:80}', () => {
    expect(fs.existsSync(caddyfilePath)).toBe(true);
    expect(caddyfileContent).toMatch(/:\{\$PORT:80\}/);
  });

  it('enforces route block with ordered routing rules for prod', () => {
    expect(caddyfileContent).toMatch(/route\s*\{/);

    const apiIndex = caddyfileContent.indexOf('@api');
    const adminAssetsIndex = caddyfileContent.indexOf('@admin_assets');
    const adminIndex = caddyfileContent.indexOf('@admin path');
    const facultyFallbackIndex = caddyfileContent.indexOf('handle {');

    expect(apiIndex).toBeGreaterThan(-1);
    expect(adminAssetsIndex).toBeGreaterThan(-1);
    expect(adminIndex).toBeGreaterThan(-1);
    expect(facultyFallbackIndex).toBeGreaterThan(-1);

    expect(apiIndex).toBeLessThan(adminAssetsIndex);
    expect(adminAssetsIndex).toBeLessThan(adminIndex);
    expect(adminIndex).toBeLessThan(facultyFallbackIndex);
  });

  it('routes /api and /api/* to FastAPI upstream', () => {
    expect(caddyfileContent).toMatch(/@api\s+path\s+\/api\s+\/api\/\*/);
    expect(caddyfileContent).toMatch(/reverse_proxy\s+\{\$SERVER_UPSTREAM:http:\/\/server:8000\}/);
  });

  it('serves admin assets and handles admin SPA fallback', () => {
    expect(caddyfileContent).toMatch(/@admin_assets\s+path\s+\/admin-assets\/\*/);
    expect(caddyfileContent).toMatch(
      /@admin\s+path\s+\/admin\s+\/admin\/\*\s+\/matrix\s+\/matrix\/\*\s+\/evaluation-map\s+\/evaluation-map\/\*/
    );
    expect(caddyfileContent).toMatch(/root\s+\*\s+\/srv\/admin/);
    expect(caddyfileContent).toMatch(/try_files\s+\{path\}\s+\/index\.html/);
  });

  it('serves faculty SPA as fallback for all remaining routes', () => {
    expect(caddyfileContent).toMatch(/root\s+\*\s+\/srv\/faculty/);
    expect(caddyfileContent).toMatch(/try_files\s+\{path\}\s+\/index\.html/);
  });
});
