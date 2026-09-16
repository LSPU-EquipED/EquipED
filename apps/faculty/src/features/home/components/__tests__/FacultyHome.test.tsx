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

  it('renders the faculty command ledger and storage action', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Faculty Command Ledger');
    expect(markup).toContain('Refresh');
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

  it('renders sleek workstation layout with storage action and no duplicate breadcrumbs', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Open Storage');
    expect(markup).toContain('Total Modules');
    // Verify duplicate breadcrumbs are removed
    expect(markup).not.toContain('Laguna State Polytechnic University');
    expect(markup).not.toContain('San Pablo City Campus');
  });

  it('renders purposeful subtitles across cards and pulse strip without AI slop', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    // Pulse strip subtitles
    expect(markup).toContain('Course SLMs in repository');
    expect(markup).toContain('Completed intake &amp; ready');
    expect(markup).toContain('Parsing syllabus &amp; content');

    // Launchpads subtitles
    expect(markup).toContain('Manage learning modules, review extraction health, and track syllabus mapping.');
    expect(markup).toContain('Inspect OCR page extractions and course materials');
    expect(markup).toContain('Verify prerequisite maps and curriculum compliance.');
    expect(markup).toContain('Check topic coverage against approved syllabi.');
    expect(markup).toContain('Access previous QA scorecards, adjectival ratings, and official PDF exports.');

    // Ledger title without redundant subtitle
    expect(markup).toContain('Faculty Command Ledger');
    expect(markup).not.toContain('Audit trail of evaluation runs and attention flags');
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

  it('surfaces specialist evaluation domains in launchpads without AI slop tags', () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain('Subject Matter Expert');
    expect(markup).toContain('Program Coordinator');
    expect(markup).toContain('Gender &amp; Development');
    expect(markup).toContain('Innovation &amp; IP (ITSO)');

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

    expect(markup).toContain('Your Assigned Evaluation Workstation');
    expect(markup).toContain('Open SME Workspace');
    expect(markup).not.toContain('Open Coordinator Workspace');
  });
});
