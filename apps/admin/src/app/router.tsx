import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  lazyRouteComponent,
  redirect,
} from '@tanstack/react-router';
import { AppShell } from './layout/AppShell';
import { appRouterContext } from './runtime';
import type { AppRouterContext } from './runtime';
import { requireRole, navigateCrossApp } from '@equiped/auth';

// Lazy Admin Pages
const AdminHomePage = lazyRouteComponent(
  () => import('../features/home/pages/AdminHomePage'),
  'AdminHomePage',
);
const UserManagementPage = lazyRouteComponent(
  () => import('../features/user-management/pages/UserManagementPage'),
  'UserManagementPage',
);
const AdminUploadPage = lazyRouteComponent(
  () => import('../features/reference-ingestion/pages/AdminUploadPage'),
  'AdminUploadPage',
);
const ReferenceLibraryPage = lazyRouteComponent(
  () => import('../features/reference-library/pages/ReferenceLibraryPage'),
  'ReferenceLibraryPage',
);
const AgentPromptPage = lazyRouteComponent(
  () => import('../features/agent-prompt/pages/AgentPromptPage'),
  'AgentPromptPage',
);
const PreferenceLogPage = lazyRouteComponent(
  () => import('../features/preference-log/pages/PreferenceLogPage'),
  'PreferenceLogPage',
);
const RubricEditorPage = lazyRouteComponent(
  () => import('../features/rubric-editor/pages/RubricEditorPage'),
  'RubricEditorPage',
);
const ModelValidationPage = lazyRouteComponent(
  () => import('../features/model-validation/pages/ModelValidationPage'),
  'ModelValidationPage',
);
const MasterSynthesisPage = lazyRouteComponent(
  () => import('../features/monitoring-matrix/pages/MasterSynthesisPage'),
  'MasterSynthesisPage',
);
const MonitoringPage = lazyRouteComponent(
  () => import('../features/monitoring-matrix/pages/MonitoringPage'),
  'MonitoringPage',
);
const EvaluationMapPage = lazyRouteComponent(
  () => import('../features/evaluation-map/pages/EvaluationMapPage'),
  'EvaluationMapPage',
);
const TrainingDataPage = lazyRouteComponent(
  () => import('../features/training-data/pages/TrainingDataPage'),
  'TrainingDataPage',
);

const rootRoute = createRootRouteWithContext<AppRouterContext>()({
  component: Outlet,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: ({ context }) => {
    if (context.auth.status !== 'authenticated') {
      navigateCrossApp('/login');
      return;
    }
    if (context.auth.user?.role !== 'admin') {
      navigateCrossApp('/dashboard');
      return;
    }
    throw redirect({ to: '/admin' });
  },
  component: () => null,
});

const shellRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'shell',
  beforeLoad: ({ context }) => {
    if (context.auth.status !== 'authenticated' || !context.auth.user) {
      navigateCrossApp('/login');
      return;
    }
    if (context.auth.user?.role !== 'admin') {
      navigateCrossApp('/dashboard');
      return;
    }
  },
  component: AppShell,
});

const adminRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'admin',
  beforeLoad: requireRole(['admin']),
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

const adminTrainingDataRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'training-data',
  beforeLoad: ({ location }) => {
    if (location.pathname === '/admin/training-data') {
      throw redirect({ to: '/admin/training-data/$agentId', params: { agentId: 'coordinator' } });
    }
  },
  component: Outlet,
});

const adminTrainingDataDetailRoute = createRoute({
  getParentRoute: () => adminTrainingDataRoute,
  path: '$agentId',
  component: TrainingDataPage,
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

const adminSynthesisRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'synthesis/$documentId',
  beforeLoad: requireRole(['admin']),
  component: MasterSynthesisPage,
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

const matrixDocumentRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'matrix/$documentId',
  beforeLoad: requireRole(['admin']),
  component: MasterSynthesisPage,
});

const evaluationMapRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluation-map',
  beforeLoad: requireRole(['admin']),
  component: EvaluationMapPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  shellRoute.addChildren([
    adminRoute.addChildren([
      adminHomeRoute,
      adminUsersRoute,
      adminIngestRoute,
      adminReferencesRoute,
      adminPromptsRoute.addChildren([adminPromptDetailRoute]),
      adminTrainingDataRoute.addChildren([adminTrainingDataDetailRoute]),
      adminPreferencesRoute,
      adminRubricsRoute,
      adminModelValidationRoute,
      adminSynthesisRoute,
    ]),
    matrixRoute,
    matrixDocumentRoute,
    evaluationMapRoute,
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
