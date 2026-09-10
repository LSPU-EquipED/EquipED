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
import { requireRole, requireEvaluatorPermission } from '../features/auth/guards/RoleGuard';
import { useAuth } from '../features/auth/hooks/useAuth';
import { resolveUploadRouteAccess } from '../features/upload/utils/uploadFlow';
import { isTargetAgent } from '@/shared/types/evaluations';

// Lazy Feature Pages
const FacultyHomePage = lazyRouteComponent(
  () => import('../features/home/pages/FacultyHomePage'),
  'FacultyHomePage',
);
const DocumentsPage = lazyRouteComponent(
  () => import('../features/documents/pages/DocumentsPage'),
  'DocumentsPage',
);
const LoginPage = lazyRouteComponent(() => import('../features/auth/pages/LoginPage'), 'LoginPage');
const RegistrationPage = lazyRouteComponent(
  () => import('../features/auth/pages/RegistrationPage'),
  'RegistrationPage',
);
const UploadPage = lazyRouteComponent(
  () => import('../features/upload/pages/UploadPage'),
  'UploadPage',
);
const HistoryPage = lazyRouteComponent(
  () => import('../features/history/pages/HistoryPage'),
  'HistoryPage',
);
const ScorecardPage = lazyRouteComponent(
  () => import('../features/evaluation/pages/ScorecardPage'),
  'ScorecardPage',
);
const SpecialistScoreboardPage = lazyRouteComponent(
  () => import('../features/evaluation/pages/SpecialistScoreboardPage'),
  'SpecialistScoreboardPage',
);
const MonitoringPage = lazyRouteComponent(
  () => import('../features/admin/monitoring-matrix/pages/MonitoringPage'),
  'MonitoringPage',
);
const AlignmentCheckPage = lazyRouteComponent(
  () => import('../features/alignment/curriculum/pages/AlignmentCheckPage'),
  'AlignmentCheckPage',
);
const SyllabusAlignmentPage = lazyRouteComponent(
  () => import('../features/alignment/syllabus/pages/SyllabusAlignmentPage'),
  'SyllabusAlignmentPage',
);
const SyllabusAlignmentWorkspacePage = lazyRouteComponent(
  () => import('../features/alignment/syllabus/pages/SyllabusAlignmentWorkspacePage'),
  'SyllabusAlignmentWorkspacePage',
);
const SyllabusAlignmentReportPage = lazyRouteComponent(
  () => import('../features/alignment/syllabus/pages/SyllabusAlignmentReportPage'),
  'SyllabusAlignmentReportPage',
);
const EvaluationMapPage = lazyRouteComponent(
  () => import('../features/admin/evaluation-map/pages/EvaluationMapPage'),
  'EvaluationMapPage',
);

// Lazy Admin Pages
const AdminHomePage = lazyRouteComponent(
  () => import('../features/admin/home/pages/AdminHomePage'),
  'AdminHomePage',
);
const UserManagementPage = lazyRouteComponent(
  () => import('../features/admin/user-management/pages/UserManagementPage'),
  'UserManagementPage',
);
const AdminUploadPage = lazyRouteComponent(
  () => import('../features/admin/reference-ingestion/pages/AdminUploadPage'),
  'AdminUploadPage',
);
const ReferenceLibraryPage = lazyRouteComponent(
  () => import('../features/admin/reference-library/pages/ReferenceLibraryPage'),
  'ReferenceLibraryPage',
);
const AgentPromptPage = lazyRouteComponent(
  () => import('../features/admin/agent-prompt/pages/AgentPromptPage'),
  'AgentPromptPage',
);
const PreferenceLogPage = lazyRouteComponent(
  () => import('../features/admin/preference-log/pages/PreferenceLogPage'),
  'PreferenceLogPage',
);
const RubricEditorPage = lazyRouteComponent(
  () => import('../features/admin/rubric-editor/pages/RubricEditorPage'),
  'RubricEditorPage',
);
const ModelValidationPage = lazyRouteComponent(
  () => import('../features/admin/model-validation/pages/ModelValidationPage'),
  'ModelValidationPage',
);
const MasterSynthesisPage = lazyRouteComponent(
  () => import('../features/admin/monitoring-matrix/pages/MasterSynthesisPage'),
  'MasterSynthesisPage',
);

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

const registrationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'register',
  beforeLoad: ({ context }) => {
    if (context.auth.status === 'authenticated') throw redirect({ to: '/dashboard' });
  },
  component: RegistrationPage,
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
  beforeLoad: requireRole(['faculty']),
  component: FacultyHomePage,
});
function DocumentsRouteView() {
  const { user } = useAuth();
  const firstPermission = user?.evaluatorPermissions?.[0];
  const targetAgent = isTargetAgent(firstPermission) ? firstPermission : 'sme';
  return <DocumentsPage targetAgent={targetAgent} />;
}


const documentsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'documents',
  beforeLoad: requireRole(['faculty']),
  component: DocumentsRouteView,
});

function UploadRouteView() {
  const { user } = useAuth();
  const firstPermission = user?.evaluatorPermissions?.[0];
  const targetAgent = isTargetAgent(firstPermission) ? firstPermission : 'sme';
  return (
    <div className="px-6 py-7">
      <UploadPage user={user} targetAgent={targetAgent} />
    </div>
  );
}

const uploadRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'upload',
  beforeLoad: ({ context }) => {
    const access = resolveUploadRouteAccess(context.auth.user?.role);
    if (!access.allowed) {
      throw redirect({ to: access.redirectTo });
    }
  },
  component: UploadRouteView,
});

function EvaluationsRouteView() {
  const auth = useAuth();
  return (
    <div className="px-6 py-7">
      <HistoryPage
        evaluatorPermissions={auth.user?.evaluatorPermissions}
        userRole={auth.user?.role}
      />
    </div>
  );
}

const evaluationsRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations',
  beforeLoad: requireRole(['faculty']),
  component: EvaluationsRouteView,
});

const evaluationMapRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluation-map',
  beforeLoad: requireRole(['admin']),
  component: EvaluationMapPage,
});

const documentEvaluationRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'documents/$documentId/evaluation',
  beforeLoad: ({ context, params, search }) => {
    requireRole(['faculty'])({ context });
    const searchRecord = search as Record<string, unknown> | undefined;
    const rawTarget = searchRecord?.target_agent;
    const firstPermission = context.auth?.user?.evaluatorPermissions?.[0];
    const fallbackTarget = isTargetAgent(firstPermission) ? firstPermission : 'sme';
    const target =
      typeof rawTarget === 'string' && isTargetAgent(rawTarget) ? rawTarget : fallbackTarget;
    requireEvaluatorPermission(() => target)({ context, params });
    throw redirect({
      to: '/specialists/$agentId/$documentId',
      params: { agentId: target, documentId: params.documentId },
    });
  },
});

const specialistScoreboardDocRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'specialists/$agentId/$documentId',
  beforeLoad: ({ context, params }) => {
    requireRole(['faculty'])({ context });
    requireEvaluatorPermission((p) => p.agentId)({ context, params });
  },
  component: SpecialistScoreboardPage,
});

const specialistScoreboardRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'specialists/$agentId',
  beforeLoad: ({ context, params }) => {
    requireRole(['faculty'])({ context });
    requireEvaluatorPermission((p) => p.agentId)({ context, params });
  },
  component: SpecialistScoreboardPage,
});

const evaluationDetailRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'evaluations/$id',
  beforeLoad: requireRole(['faculty']),
  component: ScorecardPage,
});

const storageRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'storage',
  beforeLoad: () => {
    throw redirect({ to: '/documents' });
  },
});
const syllabusAlignmentRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'syllabus-alignment',
  beforeLoad: requireRole(['faculty']),
  component: SyllabusAlignmentPage,
});

const syllabusAlignmentWorkspaceRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'syllabus-alignment/$documentId',
  beforeLoad: requireRole(['faculty']),
  component: SyllabusAlignmentWorkspacePage,
});

const syllabusAlignmentReportRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'syllabus-alignment/$documentId/report',
  beforeLoad: requireRole(['faculty']),
  component: SyllabusAlignmentReportPage,
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
  beforeLoad: requireRole(['faculty']),
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

const adminSynthesisRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'synthesis/$documentId',
  beforeLoad: ({ context }) => {
    requireRole(['admin'])({ context });
  },
  component: MasterSynthesisPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registrationRoute,
  shellRoute.addChildren([
    dashboardRoute,
    documentsRoute,
    uploadRoute,
    evaluationsRoute,
    evaluationMapRoute,
    documentEvaluationRoute,
    storageRoute,
    specialistScoreboardDocRoute,
    specialistScoreboardRoute,
    evaluationDetailRoute,
    syllabusAlignmentRoute,
    syllabusAlignmentWorkspaceRoute,
    syllabusAlignmentReportRoute,
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
      adminSynthesisRoute,
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
