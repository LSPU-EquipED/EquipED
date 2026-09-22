import { describe, expect, it } from 'vitest';
import { requireRole, requireEvaluatorPermission, type AuthRouterContext } from '../RoleGuard';

describe('RoleGuard and EvaluatorPermission guards', () => {
  const createContext = (
    status: 'anonymous' | 'authenticated',
    user: { id: string; displayName: string; role: 'admin' | 'faculty'; email: string; evaluatorPermissions?: string[] } | null,
  ): AuthRouterContext => ({
    auth: {
      status,
      user,
    },
  });

  describe('requireRole', () => {
    it('redirects unauthenticated users to default login route', () => {
      const guard = requireRole(['faculty']);
      const context = createContext('anonymous', null);

      let thrown: any;
      try {
        guard({ context });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/login');
    });

    it('redirects unauthenticated users to custom redirect route', () => {
      const guard = requireRole(['faculty'], '/custom-login');
      const context = createContext('anonymous', null);

      let thrown: any;
      try {
        guard({ context });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/custom-login');
    });

    it('allows authenticated users with permitted role', () => {
      const guard = requireRole(['faculty']);
      const context = createContext('authenticated', {
        id: 'user-1',
        displayName: 'Faculty Member',
        role: 'faculty',
        email: 'faculty@lspu.edu.ph',
      });

      expect(() => guard({ context })).not.toThrow();
    });

    it('redirects unauthorized admin user to /admin fallback', () => {
      const guard = requireRole(['faculty']);
      const context = createContext('authenticated', {
        id: 'admin-1',
        displayName: 'Admin User',
        role: 'admin',
        email: 'admin@lspu.edu.ph',
      });

      let thrown: any;
      try {
        guard({ context });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.href ?? thrown.options?.to ?? thrown.to).toBe('/admin');
    });

    it('redirects unauthorized faculty user to /dashboard fallback', () => {
      const guard = requireRole(['admin']);
      const context = createContext('authenticated', {
        id: 'faculty-1',
        displayName: 'Faculty User',
        role: 'faculty',
        email: 'faculty@lspu.edu.ph',
      });

      let thrown: any;
      try {
        guard({ context });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/dashboard');
    });

    it('redirects unauthorized user to custom unauthorizedRedirectTo', () => {
      const guard = requireRole(['admin'], '/login', '/403');
      const context = createContext('authenticated', {
        id: 'faculty-1',
        displayName: 'Faculty User',
        role: 'faculty',
        email: 'faculty@lspu.edu.ph',
      });

      let thrown: any;
      try {
        guard({ context });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/403');
    });
  });

  describe('requireEvaluatorPermission', () => {
    const getAgentId = (params: Record<string, string>) => params.agentId;

    it('redirects unauthenticated users to /login', () => {
      const guard = requireEvaluatorPermission(getAgentId);
      const context = createContext('anonymous', null);

      let thrown: any;
      try {
        guard({ context, params: { agentId: 'sme' } });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/login');
    });

    it('always permits admin users regardless of permissions', () => {
      const guard = requireEvaluatorPermission(getAgentId);
      const context = createContext('authenticated', {
        id: 'admin-1',
        displayName: 'Admin User',
        role: 'admin',
        email: 'admin@lspu.edu.ph',
        evaluatorPermissions: ['coordinator'],
      });

      expect(() => guard({ context, params: { agentId: 'sme' } })).not.toThrow();
    });

    it('permits faculty when evaluatorPermissions are undefined, null, or empty (unrestricted)', () => {
      const guard = requireEvaluatorPermission(getAgentId);

      const ctxUndefined = createContext('authenticated', {
        id: 'f-1',
        displayName: 'Faculty',
        role: 'faculty',
        email: 'f@lspu.edu.ph',
        evaluatorPermissions: undefined,
      });
      expect(() => guard({ context: ctxUndefined, params: { agentId: 'sme' } })).not.toThrow();

      const ctxEmpty = createContext('authenticated', {
        id: 'f-2',
        displayName: 'Faculty 2',
        role: 'faculty',
        email: 'f2@lspu.edu.ph',
        evaluatorPermissions: [],
      });
      expect(() => guard({ context: ctxEmpty, params: { agentId: 'sme' } })).not.toThrow();
    });

    it('permits faculty who have the requested agentId in evaluatorPermissions', () => {
      const guard = requireEvaluatorPermission(getAgentId);
      const context = createContext('authenticated', {
        id: 'f-1',
        displayName: 'Faculty',
        role: 'faculty',
        email: 'f@lspu.edu.ph',
        evaluatorPermissions: ['sme', 'coordinator'],
      });

      expect(() => guard({ context, params: { agentId: 'sme' } })).not.toThrow();
    });

    it('redirects faculty lacking the requested agentId to unauthorizedRedirectTo (default /dashboard)', () => {
      const guard = requireEvaluatorPermission(getAgentId);
      const context = createContext('authenticated', {
        id: 'f-1',
        displayName: 'Faculty',
        role: 'faculty',
        email: 'f@lspu.edu.ph',
        evaluatorPermissions: ['coordinator'],
      });

      let thrown: any;
      try {
        guard({ context, params: { agentId: 'sme' } });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/dashboard');
    });

    it('redirects faculty lacking permission to custom unauthorizedRedirectTo', () => {
      const guard = requireEvaluatorPermission(getAgentId, '/custom-forbidden');
      const context = createContext('authenticated', {
        id: 'f-1',
        displayName: 'Faculty',
        role: 'faculty',
        email: 'f@lspu.edu.ph',
        evaluatorPermissions: ['coordinator'],
      });

      let thrown: any;
      try {
        guard({ context, params: { agentId: 'sme' } });
      } catch (err) {
        thrown = err;
      }

      expect(thrown).toBeDefined();
      expect(thrown.options?.to ?? thrown.to).toBe('/custom-forbidden');
    });
  });
});
