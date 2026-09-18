// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { appRouter } from '../router';
import type { AppRouterContext } from '../runtime';

describe('admin appRouter configuration and route splitting', () => {
  it('preserves the expected admin route tree structure and paths', () => {
    const flatRoutes = appRouter.routesById;

    // Root and shell routes
    expect(flatRoutes['__root__']).toBeDefined();
    expect(flatRoutes['/']).toBeDefined();
    expect(flatRoutes['/shell']).toBeDefined();

    // Admin routes
    expect(flatRoutes['/shell/admin']).toBeDefined();
    expect(flatRoutes['/shell/admin/']).toBeDefined();
    expect(flatRoutes['/shell/admin/users']).toBeDefined();
    expect(flatRoutes['/shell/admin/ingest']).toBeDefined();
    expect(flatRoutes['/shell/admin/references']).toBeDefined();
    expect(flatRoutes['/shell/admin/prompts']).toBeDefined();
    expect(flatRoutes['/shell/admin/prompts/$agentId']).toBeDefined();
    expect(flatRoutes['/shell/admin/training-data']).toBeDefined();
    expect(flatRoutes['/shell/admin/training-data/$agentId']).toBeDefined();
    expect(flatRoutes['/shell/admin/preferences']).toBeDefined();
    expect(flatRoutes['/shell/admin/rubrics']).toBeDefined();
    expect(flatRoutes['/shell/admin/model-validation']).toBeDefined();
    expect(flatRoutes['/shell/admin/synthesis/$documentId']).toBeDefined();
    expect(flatRoutes['/shell/matrix']).toBeDefined();
    expect(flatRoutes['/shell/matrix/$documentId']).toBeDefined();
    expect(flatRoutes['/shell/evaluation-map']).toBeDefined();

    // Faculty routes must NOT exist in admin router
    expect((flatRoutes as Record<string, unknown>)['/shell/dashboard']).toBeUndefined();
    expect((flatRoutes as Record<string, unknown>)['/shell/documents']).toBeUndefined();
    expect((flatRoutes as Record<string, unknown>)['/shell/evaluations']).toBeUndefined();
    expect((flatRoutes as Record<string, unknown>)['/shell/syllabus-alignment']).toBeUndefined();
  });

  it('runs admin role guards beforeLoad synchronously without loading lazy components', async () => {
    const adminRoute = appRouter.routesById['/shell/admin'];
    expect(adminRoute.options.beforeLoad).toBeTypeOf('function');

    const facultyContext: AppRouterContext = {
      queryClient: appRouter.options.context.queryClient,
      auth: {
        status: 'authenticated',
        source: 'server',
        ready: true,
        error: null,
        user: {
          id: 'faculty-1',
          displayName: 'Faculty User',
          role: 'faculty',
          email: 'faculty@lspu.edu.ph',
        },
        login: async () => undefined,
        logout: async () => undefined,
        refresh: async () => undefined,
        clearError: () => undefined,
      },
    };

    let forbiddenRedirect: any;
    try {
      await adminRoute.options.beforeLoad!({
        context: facultyContext,
      } as any);
    } catch (err) {
      forbiddenRedirect = err;
    }

    expect(forbiddenRedirect).toBeDefined();
  });

  it('allows authorized admin role through beforeLoad guards', async () => {
    const adminRoute = appRouter.routesById['/shell/admin'];
    const adminContext: AppRouterContext = {
      queryClient: appRouter.options.context.queryClient,
      auth: {
        status: 'authenticated',
        source: 'server',
        ready: true,
        error: null,
        user: {
          id: 'admin-1',
          displayName: 'Admin User',
          role: 'admin',
          email: 'admin@lspu.edu.ph',
        },
        login: async () => undefined,
        logout: async () => undefined,
        refresh: async () => undefined,
        clearError: () => undefined,
      },
    };

    let thrown = false;
    try {
      await adminRoute.options.beforeLoad!({
        context: adminContext,
      } as any);
    } catch {
      thrown = true;
    }

    expect(thrown).toBe(false);
  });

  it('redirects cross-app non-admin or unauthenticated user via document navigation on index and shell', async () => {
    const assignMock = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...originalLocation, assign: assignMock },
    });

    try {
      const facultyContext: AppRouterContext = {
        queryClient: appRouter.options.context.queryClient,
        auth: {
          status: 'authenticated',
          source: 'server',
          ready: true,
          error: null,
          user: {
            id: 'faculty-1',
            displayName: 'Faculty User',
            role: 'faculty',
            email: 'faculty@lspu.edu.ph',
          },
          login: async () => undefined,
          logout: async () => undefined,
          refresh: async () => undefined,
          clearError: () => undefined,
        },
      };

      const unauthContext: AppRouterContext = {
        queryClient: appRouter.options.context.queryClient,
        auth: {
          status: 'anonymous',
          source: 'provisional',
          ready: true,
          error: null,
          user: null,
          login: async () => undefined,
          logout: async () => undefined,
          refresh: async () => undefined,
          clearError: () => undefined,
        },
      };

      const indexRoute = appRouter.routesById['/'];
      await indexRoute.options.beforeLoad!({ context: facultyContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/dashboard');

      assignMock.mockClear();
      await indexRoute.options.beforeLoad!({ context: unauthContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/login');

      assignMock.mockClear();
      const shellRoute = appRouter.routesById['/shell'];
      await shellRoute.options.beforeLoad!({ context: facultyContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/dashboard');

      assignMock.mockClear();
      await shellRoute.options.beforeLoad!({ context: unauthContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/login');
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
    }
  });
});
