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

  it('renders header with Refresh and Upload SLM action', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Faculty Command Ledger');
    expect(markup).toContain('Refresh');
    expect(markup).toContain('Upload SLM');
    expect(markup).toContain('href="/upload"');
  });

  it('renders the academic launchpads and unified metric ledger strip', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    // Launchpads
    expect(markup).toContain('SLM Storage Repository');
    expect(markup).toContain('Curriculum Alignment');
    expect(markup).toContain('Syllabus Alignment');
    expect(markup).toContain('Evaluation History');

    // Metrics
    expect(markup).toContain('Total Modules');
    expect(markup).toContain('Ready for Review');
    expect(markup).toContain('In Ingestion');
    expect(markup).toContain('Action Required');
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
});
