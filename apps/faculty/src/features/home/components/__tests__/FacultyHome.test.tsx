import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { FacultyHome } from '../FacultyHome';
import type { useFacultyHome } from '../../hooks/useFacultyHome';

const mockUseFacultyHome = vi.fn();

vi.mock('../../hooks/useFacultyHome', () => ({
  useFacultyHome: () => mockUseFacultyHome(),
}));

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    params,
    children,
    className,
  }: {
    to: string;
    params?: Record<string, string>;
    children?: React.ReactNode;
    className?: string;
  }) => {
    let href = to;
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} className={className}>
        {children}
      </a>
    );
  },
}));

describe('FacultyHome', () => {
  afterEach(() => vi.useRealTimers());
  const defaultHomeState = {
    isLoading: false,
    isError: false,
    error: null,
    stats: { total: 1, ready: 1, processing: 0, failed: 0 },
    homeData: {
      recentIssues: [],
      activeEvaluation: null,
    },
    evaluations: [
      {
        evaluation_id: 'eval-1',
        document_id: 'doc-1',
        document_title: 'Operating Systems Module',
        syllabus_id: 'syl-1',
        curriculum_id: 'curr-1',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T12:00:00Z',
      },
    ],
    refetch: vi.fn(),
  } satisfies ReturnType<typeof useFacultyHome>;

  it('renders evaluation activity and the module overview', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Evaluation activity');
    expect(markup).toContain('Module overview');
  });

  it('renders document processing metrics', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Total modules');
    expect(markup).toContain('Processed');
    expect(markup).toContain('Processing');
    expect(markup).toContain('Failed uploads');
  });

  it('renders operational ledger with recent evaluations and view scorecard links', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Recent evaluations');
    expect(markup).toContain('Operating Systems Module');
    expect(markup).toContain('Completed');
    expect(markup).toContain('View details');
    expect(markup).toContain('href="/evaluations/eval-1"');
  });

  it('renders empty state guidance when no evaluations exist yet', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      evaluations: [],
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('No evaluations on record');
  });

  it.each([
    [8, 'Good morning, Jeremy.'],
    [14, 'Good afternoon, Jeremy.'],
    [20, 'Good evening, Jeremy.'],
  ])('greets the signed-in user at local hour %s without a dashboard upload shortcut', (hour, greeting) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 1, hour));
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome displayName="Jeremy Garin" />);
    expect(markup).toContain(greeting);
    expect(markup).toMatch(/datetime="2026-10-01"/i);
    expect(markup).not.toContain('Upload module');
    expect(markup).not.toContain('href="/documents?upload=true"');
  });

  it('uses a greeting without a name when profile details are unavailable', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 1, 8));
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome displayName="  " />);
    expect(markup).toContain('Good morning.');
    expect(markup).not.toContain('undefined');
  });

  it('renders active evaluation banner when evaluation is in progress', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: 'eval-in-progress-1234',
          target_agent: 'sme',
          document_id: 'doc-1',
          document_title: 'Operating Systems Module',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'EVALUATING',
          submitted_at: '2026-08-20T12:00:00Z',
        },
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Specialist review');
    expect(markup).toContain('View progress');
    expect(markup).toContain('href="/specialists/sme/doc-1"');
    expect(markup).toContain('Operating Systems Module');
  });

  it('links all-agent active evaluations to the combined scorecard', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: 'eval-all-1234',
          document_id: 'doc-1',
          document_title: 'Operating Systems Module',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'EVALUATING',
          target_agent: 'all',
          submitted_at: '2026-08-20T12:00:00Z',
        },
      },
    });

    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('View progress');
    expect(markup).toContain('/evaluations/eval-all-1234');
    expect(markup).not.toContain('/specialists/sme/doc-1');
  });

  it.each([undefined, null, []])('shows all shortcuts for unrestricted assignments (%s)', (evaluatorPermissions) => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome evaluatorPermissions={evaluatorPermissions} />);
    for (const agent of ['sme', 'coordinator', 'gad', 'itso']) {
      expect(markup).toContain(`href="/specialists/${agent}"`);
    }
    expect(markup).toContain('href="/syllabus-alignment"');
    expect(markup).toContain('href="/curriculum-alignment"');
  });

  it('limits specialist shortcuts to the assigned workspaces while retaining alignment checks', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome evaluatorPermissions={['coordinator', 'gad']} />);
    expect(markup).toContain('href="/specialists/coordinator"');
    expect(markup).toContain('href="/specialists/gad"');
    expect(markup).not.toContain('href="/specialists/sme"');
    expect(markup).not.toContain('href="/specialists/itso"');
    expect(markup).toContain('href="/syllabus-alignment"');
    expect(markup).toContain('href="/curriculum-alignment"');
  });

  it('shows every specialist to admins regardless of assignments', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome userRole="admin" evaluatorPermissions={['sme']} />);
    for (const agent of ['sme', 'coordinator', 'gad', 'itso']) {
      expect(markup).toContain(`href="/specialists/${agent}"`);
    }
  });

});
