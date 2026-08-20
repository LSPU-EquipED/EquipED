import { describe, expect, it } from 'vitest';
import { appRouter } from '../router';
import type { AppRouterContext } from '../runtime';

describe('appRouter configuration and route splitting', () => {
  it('preserves the expected route tree structure and paths', () => {
    const flatRoutes = appRouter.routesById;

    // Root and shell routes
    expect(flatRoutes['__root__']).toBeDefined();
    expect(flatRoutes['/']).toBeDefined();
    expect(flatRoutes['/login']).toBeDefined();
    expect(flatRoutes['/shell']).toBeDefined();

    // Faculty routes
    expect(flatRoutes['/shell/dashboard']).toBeDefined();
    expect(flatRoutes['/shell/documents']).toBeDefined();
    expect(flatRoutes['/shell/upload']).toBeDefined();
    expect(flatRoutes['/shell/evaluations']).toBeDefined();
    expect(flatRoutes['/shell/evaluation-map']).toBeDefined();
    expect(flatRoutes['/shell/documents/$documentId/evaluation']).toBeDefined();
    expect(flatRoutes['/shell/evaluations/$id']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment/$documentId']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment/$documentId/report']).toBeDefined();
    expect(flatRoutes['/shell/matrix']).toBeDefined();
    expect(flatRoutes['/shell/alignment']).toBeDefined();

    // Admin routes
    expect(flatRoutes['/shell/admin']).toBeDefined();
    expect(flatRoutes['/shell/admin/']).toBeDefined();
    expect(flatRoutes['/shell/admin/users']).toBeDefined();
    expect(flatRoutes['/shell/admin/ingest']).toBeDefined();
    expect(flatRoutes['/shell/admin/references']).toBeDefined();
    expect(flatRoutes['/shell/admin/prompts']).toBeDefined();
    expect(flatRoutes['/shell/admin/prompts/$agentId']).toBeDefined();
    expect(flatRoutes['/shell/admin/preferences']).toBeDefined();
    expect(flatRoutes['/shell/admin/rubrics']).toBeDefined();
    expect(flatRoutes['/shell/admin/model-validation']).toBeDefined();
  });

  it('runs eager role guards beforeLoad synchronously without loading lazy components', async () => {
    const dashboardRoute = appRouter.routesById['/shell/dashboard'];
    expect(dashboardRoute.options.beforeLoad).toBeTypeOf('function');

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

    // Faculty guard redirect on unauthenticated
    let redirectError: any;
    try {
      await dashboardRoute.options.beforeLoad!({
        context: unauthContext,
      } as any);
    } catch (err) {
      redirectError = err;
    }

    expect(redirectError).toBeDefined();
    expect(redirectError.options?.to ?? redirectError.to).toBe('/login');

    // Faculty guard redirect for admin role
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

    let forbiddenRedirect: any;
    try {
      await dashboardRoute.options.beforeLoad!({
        context: adminContext,
      } as any);
    } catch (err) {
      forbiddenRedirect = err;
    }

    expect(forbiddenRedirect).toBeDefined();
    expect(forbiddenRedirect.options?.to ?? forbiddenRedirect.to).toBe('/admin');
  });

  it('allows authorized roles through beforeLoad guards', async () => {
    const dashboardRoute = appRouter.routesById['/shell/dashboard'];
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

    // Should not throw
    const result = await dashboardRoute.options.beforeLoad!({
      context: facultyContext,
    } as any);
    expect(result).toBeUndefined();
  });
});
