import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { createServer, type ViteDevServer } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { createServer as createNetServer, type AddressInfo } from 'node:net';

describe('Vite Dev Proxy and Route Smoke Tests', () => {
  let facultyServer: ViteDevServer;
  let adminServer: ViteDevServer;
  let facultyPort: number;
  let adminPort: number;

  beforeAll(async () => {
    // Reserve OS-assigned ports so concurrent workspace projects cannot claim
    // the production development ports. The proxy targets are injected below,
    // while the inline config mirrors each app's real Vite setup.
    const adminReservation = await reservePort();
    const adminPortCandidate = adminReservation.port;
    adminServer = await createServer({
      configFile: false,
      root: path.resolve(__dirname, '../../../../admin'),
      base: '/admin-dev/',
      build: { assetsDir: 'admin-assets' },
      plugins: [react(), tailwindcss(), {
        name: 'admin-spa-route-entry-test',
        configureServer(server) {
          server.middlewares.use((req, _res, next) => {
            if (req.url && /^\/(admin|matrix|evaluation-map)(\/|$)/.test(req.url)) req.url = '/';
            next();
          });
        },
      }],
      resolve: { alias: { '@': path.resolve(__dirname, '../../../../admin/src') } },
      server: { host: '127.0.0.1', port: adminPortCandidate, strictPort: true },
    });
    await adminReservation.release();
    await adminServer.listen();
    adminPort = getListeningPort(adminServer);

    const facultyReservation = await reservePort();
    const facultyPortCandidate = facultyReservation.port;
    facultyServer = await createServer({
      configFile: false,
      root: path.resolve(__dirname, '../../../'),
      plugins: [react(), tailwindcss()],
      resolve: { alias: { '@': path.resolve(__dirname, '../../../src') } },
      server: {
        host: '127.0.0.1',
        port: facultyPortCandidate,
        strictPort: true,
        proxy: {
          '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
          '/admin-assets': { target: `http://127.0.0.1:${adminPort}`, changeOrigin: true },
          '/admin': { target: `http://127.0.0.1:${adminPort}`, changeOrigin: true },
          '/matrix': { target: `http://127.0.0.1:${adminPort}`, changeOrigin: true },
          '/evaluation-map': { target: `http://127.0.0.1:${adminPort}`, changeOrigin: true },
        },
      },
    });
    await facultyReservation.release();
    await facultyServer.listen();
    facultyPort = getListeningPort(facultyServer);
  }, 30000);

  async function reservePort(): Promise<{ port: number; release: () => Promise<void> }> {
    const probe = createNetServer();
    await new Promise<void>((resolve, reject) => {
      probe.once('error', reject);
      probe.listen(0, '127.0.0.1', () => resolve());
    });
    const address = probe.address() as AddressInfo;
    return { port: address.port, release: () => new Promise<void>((resolve, reject) =>
      probe.close((error) => error ? reject(error) : resolve())), };
  }

  function getListeningPort(server: ViteDevServer): number {
    const address = server.httpServer?.address();
    if (!address || typeof address === 'string') {
      throw new Error('Vite test server did not bind to a TCP port');
    }
    return (address as AddressInfo).port;
  }

  // Fetch keeps HTTP connections alive. Close the watcher and HTTP listener
  // directly so shutdown does not wait on Vite's canceled build cleanup.
  async function closeDevServer(server: ViteDevServer | undefined) {
    if (!server) return;
    (server.httpServer as typeof server.httpServer & {
      closeAllConnections?: () => void;
    })?.closeAllConnections?.();
    await server.watcher.close();
    if (server.httpServer?.listening) {
      await new Promise<void>((resolve, reject) =>
        server.httpServer!.close((error) => (error ? reject(error) : resolve())),
      );
    }
  }

  afterAll(async () => {
    await Promise.all([
      closeDevServer(facultyServer),
      closeDevServer(adminServer),
    ]);
  }, 30000);

  async function fetchThroughFaculty(routePath: string) {
    const res = await fetch(`http://localhost:${facultyPort}${routePath}`);
    const text = await res.text();
    return { status: res.status, headers: res.headers, text };
  }

  async function expectEntry(routePath: string, entryPath: string, marker: string) {
    const page = await fetchThroughFaculty(routePath);
    expect(page.status).toBe(200);
    const match = [...page.text.matchAll(/<script[^>]+type="module"[^>]+src="([^"]+)"/g)]
      .find((candidate) => candidate[1].endsWith('/src/main.tsx'));
    expect(match).not.toBeNull();
    expect(match![1]).toBe(entryPath);
    const entry = await fetch(`http://localhost:${facultyPort}${entryPath}`);
    expect(entry.status).toBe(200);
    expect(await entry.text()).toContain(marker);
  }

  it('serves Faculty HTML for canonical faculty routes', async () => {
    const facultyRoutes = ['/', '/login', '/dashboard', '/documents', '/evaluations', '/curriculum-alignment', '/alignment'];
    for (const route of facultyRoutes) {
      const { status, text } = await fetchThroughFaculty(route);
      expect(status).toBe(200);
      expect(text).toContain('EquipED - LSPU Faculty Portal');
      expect(text).not.toContain('EquipED - LSPU Admin Portal');
    }
    await expectEntry('/', '/src/main.tsx', 'createRoot');
  }, 15000);

  it('proxies bare /admin and /admin/* routes to Admin Vite server', async () => {
    const adminRoutes = ['/admin', '/admin/', '/admin/users', '/admin/ingest'];
    for (const route of adminRoutes) {
      const { status, text } = await fetchThroughFaculty(route);
      expect(status).toBe(200);
      expect(text).toContain('EquipED - LSPU Admin Portal');
      expect(text).not.toContain('EquipED - LSPU Faculty Portal');
    }
    await expectEntry('/admin', '/admin-dev/src/main.tsx', 'createRoot');
  }, 15000);

  it('proxies /matrix and descendants to Admin Vite server', async () => {
    const matrixRoutes = ['/matrix', '/matrix/', '/matrix/doc-123'];
    for (const route of matrixRoutes) {
      const { status, text } = await fetchThroughFaculty(route);
      expect(status).toBe(200);
      expect(text).toContain('EquipED - LSPU Admin Portal');
      expect(text).not.toContain('EquipED - LSPU Faculty Portal');
    }
  }, 15000);

  it('proxies /evaluation-map and descendants to Admin Vite server', async () => {
    const evalMapRoutes = ['/evaluation-map', '/evaluation-map/'];
    for (const route of evalMapRoutes) {
      const { status, text } = await fetchThroughFaculty(route);
      expect(status).toBe(200);
      expect(text).toContain('EquipED - LSPU Admin Portal');
      expect(text).not.toContain('EquipED - LSPU Faculty Portal');
    }
  }, 15000);
});
