import { Outlet, createRootRouteWithContext, createRoute, createRouter, redirect } from '@tanstack/react-router';
import { AppShell } from './layout/AppShell';
import { DashboardPage } from './DashboardPage';
import { appRouterContext } from './runtime';
import type { AppRouterContext } from './runtime';
import { LoginForm } from '../features/auth/components/LoginForm';
import { requireRole } from '../features/auth/guards/RoleGuard';
import { UploadForm } from '../features/upload/components/UploadForm';
import { EvaluationHistoryTable } from '../features/history/components/EvaluationHistoryTable';
import { EvaluationInterface } from '../features/evaluation/components/EvaluationInterface';
import { Scorecard } from '../features/evaluation/components/Scorecard';
import { ReportView } from '../features/evaluation/components/ReportView';
import { MonitoringTable } from '../features/matrix/components/MonitoringTable';
import { AdminHomePage } from '../features/admin/components/AdminHomePage';
import { UserManagementPage } from '../features/admin/components/UserManagementPage';
import { AdminUploadPage } from '../features/admin/components/AdminUploadPage';
import { AgentPromptEditor } from '../features/admin/components/AgentPromptEditor';
import { PreferenceLogTable } from '../features/admin/components/PreferenceLogTable';
import { RubricTableEditor } from '../features/admin/components/RubricTableEditor';

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
  component: LoginForm,
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
  component: UploadForm,
});

const evaluationsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations',
  component: EvaluationHistoryTable,
});

const documentEvaluationRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'documents/$documentId/evaluation',
  component: EvaluationInterface,
});

const evaluationDetailRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations/$id',
  component: Scorecard,
});

const evaluationReportRoute = createRoute({
  getParentRoute: () => evaluationDetailRoute,
  path: 'report',
  component: ReportView,
});

const matrixRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'matrix',
  beforeLoad: requireRole(['admin']),
  component: MonitoringTable,
});

const adminRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'admin',
  beforeLoad: ({ context }) => {
    requireRole(['admin'])({ context });
  },
  component: Outlet,
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
  component: AgentPromptEditor,
});

const adminPreferencesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'preferences',
  component: PreferenceLogTable,
});

const adminRubricsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'rubrics',
  component: RubricTableEditor,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  shellRoute.addChildren([
    dashboardRoute,
    uploadRoute,
    evaluationsRoute,
    documentEvaluationRoute,
    evaluationDetailRoute.addChildren([evaluationReportRoute]),
    matrixRoute,
    adminRoute.addChildren([
      adminHomeRoute,
      adminUsersRoute,
      adminIngestRoute,
      adminPromptsRoute.addChildren([adminPromptDetailRoute]),
      adminPreferencesRoute,
      adminRubricsRoute,
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
