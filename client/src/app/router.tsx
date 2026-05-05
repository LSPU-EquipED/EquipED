import { Outlet, createRootRouteWithContext, createRoute, createRouter, redirect } from '@tanstack/react-router';
import { AppShell } from './layout/AppShell';
import { DashboardPage } from './DashboardPage';
import { appRouterContext } from './runtime';
import type { AppRouterContext } from './runtime';
import { LoginForm } from '../features/auth/components/LoginForm';
import { requireRole } from '../features/auth/guards/RoleGuard';
import { UploadForm } from '../features/upload/components/UploadForm';
import { EvaluationHistoryTable } from '../features/history/components/EvaluationHistoryTable';
import { Scorecard } from '../features/evaluation/components/Scorecard';
import { ReportView } from '../features/evaluation/components/ReportView';
import { MonitoringTable } from '../features/matrix/components/MonitoringTable';
import { AgentPromptEditor } from '../features/admin/components/AgentPromptEditor';
import { PreferenceLogTable } from '../features/admin/components/PreferenceLogTable';

const rootRoute = createRootRouteWithContext<AppRouterContext>()({
  component: Outlet,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/dashboard' });
  },
  component: () => null,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'login',
  component: LoginForm,
});

const shellRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'shell',
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

const evaluationDetailRoute = createRoute({
  getParentRoute: () => evaluationsRoute,
  path: '$id',
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
  beforeLoad: requireRole(['coordinator', 'admin']),
  component: MonitoringTable,
});

const adminRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'admin',
  beforeLoad: ({ context, location }) => {
    requireRole(['admin'])({ context });

    if (location.pathname.replace(/\/$/, '') === '/admin') {
      throw redirect({ to: '/admin/prompts' });
    }
  },
  component: Outlet,
});

const adminPromptsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'prompts',
  component: AgentPromptEditor,
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

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  shellRoute.addChildren([
    dashboardRoute,
    uploadRoute,
    evaluationsRoute.addChildren([evaluationDetailRoute.addChildren([evaluationReportRoute])]),
    matrixRoute,
    adminRoute.addChildren([adminPromptsRoute.addChildren([adminPromptDetailRoute]), adminPreferencesRoute]),
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
