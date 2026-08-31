import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { FacultyHome } from '../FacultyHome';

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
  const defaultHomeState = {
    isLoading: false,
    isError: false,
    error: null,
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

  it('renders the unified metric ledger strip with total modules and completed reviews', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Total Modules');
    expect(markup).toContain('Completed Reviews');
    expect(markup).toContain('In Progress');
    expect(markup).toContain('Action Required');
  });

  it('renders operational module ledger with document details and action links', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('All Course Modules');
    expect(markup).toContain('Operating Systems Module');
    expect(markup).toContain('BSCS');
    expect(markup).toContain('Ready');
    expect(markup).toContain('Completed (Partial)');
    expect(markup).toContain('Open Evaluation');
    expect(markup).toContain('href="/documents/doc-1/evaluation"');
  });

  it('renders empty state guidance when no documents are uploaded yet', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      documents: [],
      homeData: {
        ...defaultHomeState.homeData,
        recentSlms: [],
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('No SLMs uploaded yet');
    expect(markup).toContain('Use the Upload SLM action above to add course learning materials.');
  });

  it('renders Start Evaluation button for ready documents without evaluation', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      documents: [
        {
          documentId: 'doc-2',
          title: 'Algorithms Module 2',
          program: 'BSCS',
          sourceType: 'slm',
          uploadedAt: '2026-08-21T10:00:00Z',
          processingStatus: 'PROCESSED',
        },
      ],
      latestEvalsByDocId: {},
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Algorithms Module 2');
    expect(markup).toContain('Ready to Evaluate');
    expect(markup).toContain('Start Evaluation');
    expect(markup).toContain('href="/documents/doc-2/evaluation"');
  });
});
