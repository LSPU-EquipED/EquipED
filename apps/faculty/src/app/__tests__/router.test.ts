// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { appRouter } from '../router';
import type { AppRouterContext } from '../runtime';

describe('faculty appRouter configuration and route splitting', () => {
  it('preserves the expected route tree structure and paths', () => {
    const flatRoutes = appRouter.routesById;

    // Root and shell routes
    expect(flatRoutes['__root__']).toBeDefined();
    expect(flatRoutes['/']).toBeDefined();
    expect(flatRoutes['/login']).toBeDefined();
    expect(flatRoutes['/register']).toBeDefined();
    expect(flatRoutes['/shell']).toBeDefined();

    // Faculty routes
    expect(flatRoutes['/shell/dashboard']).toBeDefined();
    expect(flatRoutes['/shell/documents']).toBeDefined();
    expect(flatRoutes['/shell/evaluations']).toBeDefined();
    expect(flatRoutes['/shell/documents/$documentId/evaluation']).toBeDefined();
    expect(flatRoutes['/shell/specialists/$agentId']).toBeDefined();
    expect(flatRoutes['/shell/specialists/$agentId/$documentId']).toBeDefined();
    expect(flatRoutes['/shell/evaluations/$id']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment/$documentId']).toBeDefined();
    expect(flatRoutes['/shell/syllabus-alignment/$documentId/report']).toBeDefined();
    expect(flatRoutes['/shell/curriculum-alignment']).toBeDefined();
    expect(flatRoutes['/shell/alignment']).toBeDefined();

    // Canonical curriculum alignment renders the page component
    const canonicalRoute = flatRoutes['/shell/curriculum-alignment'];
    expect(canonicalRoute.options.component).toBeDefined();

    // Legacy /alignment compatibility route has no component (redirects)
    const compatibilityRoute = flatRoutes['/shell/alignment'];
    expect(compatibilityRoute.options.component).toBeUndefined();

    // Admin routes must NOT exist in faculty router
    expect((flatRoutes as Record<string, unknown>)['/shell/admin']).toBeUndefined();
    expect((flatRoutes as Record<string, unknown>)['/shell/matrix']).toBeUndefined();
    expect((flatRoutes as Record<string, unknown>)['/shell/evaluation-map']).toBeUndefined();
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

    let thrown = false;
    try {
      await dashboardRoute.options.beforeLoad!({
        context: facultyContext,
      } as any);
    } catch {
      thrown = true;
    }

    expect(thrown).toBe(false);
  });

  it('redirects cross-app admin user via document navigation on index and auth routes', async () => {
    const assignMock = vi.fn();
    const originalLocation = window.location;
    // Mock window.location.assign
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { ...originalLocation, assign: assignMock },
    });

    try {
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

      const indexRoute = appRouter.routesById['/'];
      await indexRoute.options.beforeLoad!({ context: adminContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/admin');

      assignMock.mockClear();
      const loginRoute = appRouter.routesById['/login'];
      await loginRoute.options.beforeLoad!({ context: adminContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/admin');

      assignMock.mockClear();
      const registerRoute = appRouter.routesById['/register'];
      await registerRoute.options.beforeLoad!({ context: adminContext } as any);
      expect(assignMock).toHaveBeenCalledWith('/admin');
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
    }
  });

  it('enforces specialist evaluator permissions on specialist route guards', async () => {
    const specialistRoute = appRouter.routesById['/shell/specialists/$agentId'];
    expect(specialistRoute.options.beforeLoad).toBeTypeOf('function');

    const baseContext = (perms?: string[]): AppRouterContext => ({
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
          evaluatorPermissions: perms,
        },
        login: async () => undefined,
        logout: async () => undefined,
        refresh: async () => undefined,
        clearError: () => undefined,
      },
    });

    type RouteBeforeLoadFn = (args: { context: AppRouterContext; params: Record<string, string> }) => unknown;
    const beforeLoad = specialistRoute.options.beforeLoad as unknown as RouteBeforeLoadFn;

    // Allowed when user has the specific specialist permission
    const allowedResult = await beforeLoad({
      context: baseContext(['sme']),
      params: { agentId: 'sme' },
    });
    expect(allowedResult).toBeUndefined();

    // Redirected to /dashboard when user lacks the specific specialist permission
    let deniedTarget: string | undefined;
    try {
      await beforeLoad({
        context: baseContext(['sme']),
        params: { agentId: 'coordinator' },
      });
    } catch (err: unknown) {
      if (err && typeof err === 'object') {
        const errRecord = err as Record<string, unknown>;
        const options = errRecord.options as Record<string, unknown> | undefined;
        deniedTarget = typeof options?.to === 'string' ? options.to : (errRecord.to as string | undefined);
      }
    }
    expect(deniedTarget).toBe('/dashboard');

    // Allowed when permissions are unspecified (backward compatibility)
    const legacyResult = await beforeLoad({
      context: baseContext(undefined),
      params: { agentId: 'coordinator' },
    });
    expect(legacyResult).toBeUndefined();

    // ADR 0006: Invalid specialist agent route redirects to /dashboard without coercing to SME, even if permissions are unspecified
    let invalidAgentTarget: string | undefined;
    try {
      await beforeLoad({
        context: baseContext(undefined),
        params: { agentId: 'invalid-agent' },
      });
    } catch (err: unknown) {
      if (err && typeof err === 'object') {
        const errRecord = err as Record<string, unknown>;
        const options = errRecord.options as Record<string, unknown> | undefined;
        invalidAgentTarget = typeof options?.to === 'string' ? options.to : (errRecord.to as string | undefined);
      }
    }
    expect(invalidAgentTarget).toBe('/dashboard');
  });

  describe('ADR 0007: canonical /curriculum-alignment and compatibility /alignment redirect', () => {
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

    it('enforces authentication and role guards on the canonical /curriculum-alignment route', async () => {
      const canonicalRoute = appRouter.routesById['/shell/curriculum-alignment'];
      expect(canonicalRoute.options.beforeLoad).toBeTypeOf('function');

      // Unauthenticated access rejects to /login
      let unauthError: any;
      try {
        await canonicalRoute.options.beforeLoad!({ context: unauthContext } as any);
      } catch (err) {
        unauthError = err;
      }
      expect(unauthError?.options?.to ?? unauthError?.to).toBe('/login');

      // Admin (wrong role for faculty guard) redirects to /admin
      let adminError: any;
      try {
        await canonicalRoute.options.beforeLoad!({ context: adminContext } as any);
      } catch (err) {
        adminError = err;
      }
      expect(adminError?.options?.href ?? adminError?.options?.to ?? adminError?.to).toBe('/admin');

      // Faculty user passes beforeLoad guard
      expect(
        canonicalRoute.options.beforeLoad!({ context: facultyContext } as any),
      ).toBeUndefined();
    });

    it('redirects an authorized Faculty visit to /alignment -> /curriculum-alignment with replace semantics and preserves search/hash', async () => {
      const compatibilityRoute = appRouter.routesById['/shell/alignment'];
      expect(compatibilityRoute.options.beforeLoad).toBeTypeOf('function');

      // Unauthenticated access is blocked by role guard first -> /login
      let unauthError: any;
      try {
        await compatibilityRoute.options.beforeLoad!({
          context: unauthContext,
          search: {},
          location: { hash: '' },
        } as any);
      } catch (err) {
        unauthError = err;
      }
      expect(unauthError?.options?.to ?? unauthError?.to).toBe('/login');

      // Wrong role access is blocked by role guard -> /admin
      let adminError: any;
      try {
        await compatibilityRoute.options.beforeLoad!({
          context: adminContext,
          search: {},
          location: { hash: '' },
        } as any);
      } catch (err) {
        adminError = err;
      }
      expect(adminError?.options?.href ?? adminError?.options?.to ?? adminError?.to).toBe('/admin');

      // Authorized faculty visit throws redirect to /curriculum-alignment with replace: true
      let redirectErr: any;
      try {
        await compatibilityRoute.options.beforeLoad!({
          context: facultyContext,
          search: { course_id: 'CS101' },
          location: { hash: 'matrix' },
        } as any);
      } catch (err) {
        redirectErr = err;
      }

      expect(redirectErr).toBeDefined();
      const options = redirectErr.options ?? redirectErr;
      expect(options.to).toBe('/curriculum-alignment');
      expect(options.replace).toBe(true);
      expect(options.search).toEqual({ course_id: 'CS101' });
      expect(options.hash).toBe('matrix');
    });
  });
});
