import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router';
import { AppShell } from './layout/AppShell';
import { appRouterContext } from './runtime';
import type { AppRouterContext } from './runtime';

// Feature Pages
import { DashboardPage } from '../features/dashboard/pages/DashboardPage';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { requireRole } from '../features/auth/guards/RoleGuard';
import { resolveUploadRouteAccess } from '../features/upload/utils/uploadFlow';
import { UploadPage } from '../features/upload/pages/UploadPage';
import { HistoryPage } from '../features/history/pages/HistoryPage';
import { EvaluationInterfacePage } from '../features/evaluation/pages/EvaluationInterfacePage';
import { ScorecardPage } from '../features/evaluation/pages/ScorecardPage';
import { MonitoringPage } from '../features/matrix/pages/MonitoringPage';
import { AlignmentCheckPage } from '../features/curriculumAlignment/pages/AlignmentCheckPage';

// Admin Pages
import {
  AdminHomePage,
  AdminUploadPage,
  AgentPromptPage,
  ModelValidationPage,
  PreferenceLogPage,
  ReferenceLibraryPage,
  RubricEditorPage,
  UserManagementPage,
} from '../features/admin';

const rootRoute = createRootRouteWithContext<AppRouterContext>()({
  component: Outlet,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: ({ context }) => {
    if (context.auth.status !== 'authenticated') {
      throw redirect({ to: '/login' });
    }
    const target = context.auth.user?.role === 'admin' ? '/admin' : '/dashboard';
    throw redirect({ to: target });
  },
  component: () => null,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'login',
  beforeLoad: ({ context }) => {
    if (context.auth.status === 'authenticated') {
      const target = context.auth.user?.role === 'admin' ? '/admin' : '/dashboard';
      throw redirect({ to: target });
    }
  },
  component: LoginPage,
});

const shellRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'shell',
  beforeLoad: ({ context }) => {
    if (context.auth.status !== 'authenticated' || !context.auth.user) {
      throw redirect({ to: '/login' });
    }
  },
  component: AppShell,
});

const dashboardRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'dashboard',
  component: DashboardPage,
});

const uploadRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'upload',
  beforeLoad: ({ context }) => {
    const access = resolveUploadRouteAccess(context.auth.user?.role);
    if (!access.allowed) {
      throw redirect({ to: access.redirectTo });
    }
  },
  component: () => (
    <div className="px-6 py-7">
      <UploadPage />
    </div>
  ),
});

const evaluationsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations',
  component: () => (
    <div className="px-6 py-7">
      <HistoryPage />
    </div>
  ),
});

const documentEvaluationRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'documents/$documentId/evaluation',
  component: EvaluationInterfacePage,
});

const evaluationDetailRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations/$id',
  component: ScorecardPage,
});

const matrixRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'matrix',
  beforeLoad: requireRole(['admin']),
  component: () => (
    <div className="px-6 py-7">
      <MonitoringPage />
    </div>
  ),
});

const alignmentRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'alignment',
  component: AlignmentCheckPage,
});

const adminRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'admin',
  beforeLoad: ({ context }) => {
    requireRole(['admin'])({ context });
  },
  component: () => (
    <div className="px-6 py-7">
      <Outlet />
    </div>
  ),
});

const adminHomeRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/',
  component: AdminHomePage,
});

const adminUsersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'users',
  component: UserManagementPage,
});

const adminIngestRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'ingest',
  component: AdminUploadPage,
});

const adminReferencesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'references',
  component: ReferenceLibraryPage,
});

const adminPromptsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'prompts',
  beforeLoad: ({ location }) => {
    if (location.pathname === '/admin/prompts') {
      throw redirect({ to: '/admin/prompts/$agentId', params: { agentId: 'coordinator' } });
    }
  },
  component: Outlet,
});

const adminPromptDetailRoute = createRoute({
  getParentRoute: () => adminPromptsRoute,
  path: '$agentId',
  component: AgentPromptPage,
});

const adminPreferencesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'preferences',
  component: PreferenceLogPage,
});

const adminRubricsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'rubrics',
  component: RubricEditorPage,
});

const adminModelValidationRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'model-validation',
  component: ModelValidationPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  shellRoute.addChildren([
    dashboardRoute,
    uploadRoute,
    evaluationsRoute,
    documentEvaluationRoute,
    evaluationDetailRoute,
    matrixRoute,
    alignmentRoute,
    adminRoute.addChildren([
      adminHomeRoute,
      adminUsersRoute,
      adminIngestRoute,
      adminReferencesRoute,
      adminPromptsRoute.addChildren([adminPromptDetailRoute]),
      adminPreferencesRoute,
      adminRubricsRoute,
      adminModelValidationRoute,
    ]),
  ]),
]);

export const appRouter = createRouter({
  routeTree,
  context: appRouterContext,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof appRouter;
  }
}
