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
import { requireRole, requireEvaluatorPermission, useAuth, navigateCrossApp } from '@equiped/auth';
import { isTargetAgent } from '@equiped/types';

// Lazy Faculty Feature Pages
const FacultyHomePage = lazyRouteComponent(
  () => import('./pages/FacultyHomePage'),
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
const AlignmentCheckPage = lazyRouteComponent(
  () => import('../features/curriculum-alignment/pages/AlignmentCheckPage'),
  'AlignmentCheckPage',
);
const SyllabusAlignmentPage = lazyRouteComponent(
  () => import('../features/syllabus-alignment/pages/SyllabusAlignmentPage'),
  'SyllabusAlignmentPage',
);
const SyllabusAlignmentWorkspacePage = lazyRouteComponent(
  () => import('../features/syllabus-alignment/pages/SyllabusAlignmentWorkspacePage'),
  'SyllabusAlignmentWorkspacePage',
);
const SyllabusAlignmentReportPage = lazyRouteComponent(
  () => import('../features/syllabus-alignment/pages/SyllabusAlignmentReportPage'),
  'SyllabusAlignmentReportPage',
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
    if (context.auth.user?.role === 'admin') {
      navigateCrossApp('/admin');
      return;
    }
    throw redirect({ to: '/dashboard' });
  },
  component: () => null,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'login',
  beforeLoad: ({ context }) => {
    if (context.auth.status === 'authenticated') {
      if (context.auth.user?.role === 'admin') {
        navigateCrossApp('/admin');
        return;
      }
      throw redirect({ to: '/dashboard' });
    }
  },
  component: LoginPage,
});

const registrationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'register',
  beforeLoad: ({ context }) => {
    if (context.auth.status === 'authenticated') {
      if (context.auth.user?.role === 'admin') {
        navigateCrossApp('/admin');
        return;
      }
      throw redirect({ to: '/dashboard' });
    }
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

const alignmentRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'alignment',
  beforeLoad: requireRole(['faculty']),
  component: AlignmentCheckPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registrationRoute,
  shellRoute.addChildren([
    dashboardRoute,
    documentsRoute,
    evaluationsRoute,
    documentEvaluationRoute,
    storageRoute,
    specialistScoreboardDocRoute,
    specialistScoreboardRoute,
    evaluationDetailRoute,
    syllabusAlignmentRoute,
    syllabusAlignmentWorkspaceRoute,
    syllabusAlignmentReportRoute,
    alignmentRoute,
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
