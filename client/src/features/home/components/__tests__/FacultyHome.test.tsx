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
      for (const [key, value] of Object.entries(params)) {
        href = href.replace(`$${key}`, value);
      }
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
    documents: [],
    evaluations: [],
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

  it('renders exactly one in-page Upload SLM entry via HomeQuickActions', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Faculty Overview');
    expect(markup).toContain('Refresh');

    // Count occurrences of href="/upload" in the rendered markup
    const uploadLinks = markup.match(/href="\/upload"/g);
    expect(uploadLinks).toHaveLength(1);
    expect(markup).toContain('Upload SLM');
  });

  it('maintains exactly one in-page Upload SLM entry even when recent SLMs is empty', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        recentSlms: [],
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('No SLMs uploaded yet');
    expect(markup).toContain('Use the Upload SLM action above to add course learning materials.');

    // Still exactly one Upload SLM link on the page (in HomeQuickActions)
    const uploadLinks = markup.match(/href="\/upload"/g);
    expect(uploadLinks).toHaveLength(1);
  });

  it('renders Ready to Evaluate banner when an unevaluated ready SLM is present', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        latestReadyDocument: {
          documentId: 'doc-2',
          title: 'Algorithms Module 2',
          program: 'BSCS',
        },
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Ready to Evaluate');
    expect(markup).toContain('Algorithms Module 2');
    expect(markup).toContain('Start Evaluation');
    expect(markup).toContain('href="/documents/doc-2/evaluation"');
  });

  it('renders Active Evaluation banner when an evaluation is in progress', () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: 'eval-active-9',
          document_id: 'doc-1',
          document_title: 'Operating Systems Module',
          status: 'EVALUATING',
          submitted_at: '2026-08-21T10:00:00Z',
        },
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Active Evaluation');
    expect(markup).toContain('View Progress');
    expect(markup).toContain('href="/evaluations/eval-active-9"');
  });

  it('routes a completed partial Recent SLM to the workspace while Recent Evaluations stays on the scorecard', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Evaluated');
    expect(markup).toContain('Open Evaluation');
    expect(markup).toContain('href="/documents/doc-1/evaluation"');
    expect(markup).toContain('href="/evaluations/eval-1"');
  });
});
