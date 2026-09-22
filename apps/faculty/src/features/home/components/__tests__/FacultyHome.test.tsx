import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { FacultyHome } from '../FacultyHome';

const mockUseFacultyHome = vi.fn();

vi.mock('../../hooks/useFacultyHome', () => ({
  useFacultyHome: () => mockUseFacultyHome(),
}));

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
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
  const defaultHomeState = {
    isLoading: false,
    isError: false,
    error: null,
    stats: { total: 1, ready: 1, processing: 0, failed: 0 },
    evaluatingTarget: null,
    setEvaluatingTarget: vi.fn(),
    homeData: {
      recentIssues: [],
      activeEvaluation: null,
      latestReadyDocument: null,
      hasEvaluations: true,
      recentSlms: [
        {
          documentId: 'doc-1',
          title: 'Operating Systems Module',
          courseTitle: 'CS 301',
          program: 'BSCS',
          sourceType: 'slm',
          uploadedAt: '2026-08-20T10:00:00Z',
          processingStatus: 'PROCESSED',
        },
      ],
      recentEvaluations: [
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
    },
    documents: [
      {
        documentId: 'doc-1',
        title: 'Operating Systems Module',
        courseTitle: 'CS 301',
        program: 'BSCS',
        sourceType: 'slm',
        uploadedAt: '2026-08-20T10:00:00Z',
        processingStatus: 'PROCESSED',
      },
    ],
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
    latestEvalsByDocId: {
      'doc-1': {
        document_id: 'doc-1',
        evaluation_id: 'eval-1',
        status: 'COMPLETED_PARTIAL',
        submitted_at: '2026-08-20T12:00:00Z',
      },
    },
    latestEvalsState: { isSuccess: true },
    refetch: vi.fn(),
  };

  it('renders the faculty command ledger beneath the module overview', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Recent evaluation activity');
    expect(markup).toContain('Module overview');
  });

  it('renders the module overview and evaluation tools', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    // Launchpads
    expect(markup).toContain('Evaluation workspaces');
    expect(markup).toContain('Curriculum check');
    expect(markup).toContain('Syllabus alignment');

    // Metrics
    expect(markup).toContain('Total modules');
    expect(markup).toContain('Extracted');
    expect(markup).toContain('Processing');
    expect(markup).toContain('Failed uploads');
  });

  it('renders operational ledger with recent evaluations and view scorecard links', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Recent Evaluations');
    expect(markup).toContain('Operating Systems Module');
    expect(markup).toContain('Completed');
    expect(markup).toContain('View Scorecard');
    expect(markup).toContain('href="/evaluations/eval-1"');
  });

  it('renders empty state guidance when no evaluations exist yet', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      evaluations: [],
      homeData: {
        ...defaultHomeState.homeData,
        recentEvaluations: [],
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('No evaluations on record');
  });

  it('keeps the home hierarchy focused on the pulse strip without duplicate breadcrumbs', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).not.toContain('Upload SLM');
    expect(markup).toContain('Total modules');
    // Verify duplicate breadcrumbs are removed
    expect(markup).not.toContain('Laguna State Polytechnic University');
    expect(markup).not.toContain('San Pablo City Campus');
  });

  it('renders purposeful subtitles across cards and pulse strip without AI slop', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    // Pulse strip subtitles
    expect(markup).toContain('In your repository');
    expect(markup).toContain('Document processing complete');
    expect(markup).toContain('Intake or cleanup in progress');

    // Launchpads subtitles
    expect(markup).toContain('Content accuracy and mastery');

    // Ledger title without redundant subtitle
    expect(markup).toContain('Recent Evaluations');
  });

  it('renders active evaluation banner when evaluation is in progress', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: 'eval-in-progress-1234',
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

    expect(markup).toContain('Active Evaluation in Progress');
    expect(markup).toContain('Open Specialist Scoreboard');
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

    expect(markup).toContain('Open Evaluation Scorecard');
    expect(markup).toContain('/evaluations/eval-all-1234');
    expect(markup).not.toContain('/specialists/sme/doc-1');
  });

  it('surfaces specialist evaluation domains in launchpads without AI slop tags and links to canonical curriculum alignment', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Subject Matter Expert');
    expect(markup).toContain('Program Coordinator');
    expect(markup).toContain('Gender &amp; Development');
    expect(markup).toContain('Innovation and Technology Support Office');

    // Canonical curriculum alignment destination check
    expect(markup).toContain('href="/curriculum-alignment"');
    expect(markup).not.toContain('href="/alignment"');

    // Anti-slop check: verify decorative meta-tags are purged
    expect(markup).not.toContain('[CORE STORAGE]');
    expect(markup).not.toContain('[FACULTY COMMAND LEDGER]');
    expect(markup).not.toContain('[CURRICULUM MAP]');
    expect(markup).not.toContain('[SYLLABUS AUDIT]');
  });

  it('renders focused assigned specialist workstation when single permission is granted', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(
      <FacultyHome evaluatorPermissions={['sme']} />,
    );

    expect(markup).toContain('Subject Matter Expert');
    expect(markup).not.toContain('Program Coordinator');
  });
});
