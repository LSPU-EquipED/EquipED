import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { DocumentTable, DocumentTableSkeleton } from '../DocumentTable';

// Mock @tanstack/react-router Link & useNavigate
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
  Link: ({
    to,
    children,
    className,
    'aria-label': ariaLabel,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
    'aria-label'?: string;
  }) => {
    return (
      <a href={to} className={className} aria-label={ariaLabel}>
        {children}
      </a>
    );
  },
}));

const sampleDocuments: ClientDocument[] = [
  {
    documentId: 'doc-1',
    title: 'Data Structures SLM',
    courseTitle: 'CS 101 - Data Structures',
    lessonTitle: 'Module 1',
    academicYear: '2025-2026',
    courseCode: 'CS101',
    pageCount: 15,
    hasOcrPages: false,
    chunks: [],
    program: 'BSCS',
    sourceType: 'slm',
    uploadedAt: '2026-08-15T10:00:00Z',
    processingStatus: 'PROCESSED',
  },
  {
    documentId: 'doc-2',
    title: 'Intro to IT Module',
    courseTitle: 'IT 101 - Intro to IT',
    lessonTitle: 'Module 2',
    academicYear: '2025-2026',
    courseCode: 'IT101',
    pageCount: 20,
    hasOcrPages: false,
    chunks: [],
    program: 'BSInfoTech',
    sourceType: 'slm',
    uploadedAt: '2026-08-16T11:00:00Z',
    processingStatus: 'PENDING',
  },
  {
    documentId: 'doc-3',
    title: 'Failed Upload Module',
    courseTitle: 'CS 202 - Algorithms',
    lessonTitle: 'Module 3',
    academicYear: '2025-2026',
    courseCode: 'CS202',
    pageCount: 5,
    hasOcrPages: false,
    chunks: [],
    program: 'BSCS',
    sourceType: 'slm',
    uploadedAt: '2026-08-17T12:00:00Z',
    processingStatus: 'FAILED',
  },
];

describe('DocumentTable', () => {
  it('adds scope="col" to all table headers', () => {
    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={sampleDocuments}
        flashId={null}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    const thMatches = markup.match(/<th\b[^>]*>/g) || [];
    expect(thMatches.length).toBe(7);
    for (const th of thMatches) {
      expect(th).toContain('scope="col"');
    }
  });

  it('renders Ready to Evaluate and links to workspace when processed with no evaluation', () => {
    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={{}}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    expect(markup).toContain('Ready to Evaluate');
    // Both title link and action link target /documents/doc-1/evaluation
    expect(markup).toContain('href="/documents/doc-1/evaluation"');
    expect(markup).toContain('aria-label="Start evaluation for Data Structures SLM"');
  });

  it('links title and right action to the workspace when a completed partial evaluation exists', () => {
    const latestEvals: Record<string, LatestEvaluationItem> = {
      'doc-1': {
        document_id: 'doc-1',
        evaluation_id: 'eval-done-1',
        status: 'COMPLETED_PARTIAL',
        submitted_at: '2026-08-20T10:00:00Z',
        completed_at: '2026-08-20T10:05:00Z',
      },
    };

    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={latestEvals}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    expect(markup).toContain('Evaluated');
    expect(markup.match(/href="\/documents\/doc-1\/evaluation"/g)).toHaveLength(2);
    expect(markup).toContain('aria-label="Open evaluation for Data Structures SLM"');
    expect(markup).not.toContain('href="/evaluations/eval-done-1"');
  });

  it('links title and right action to the workspace when an active evaluation is running', () => {
    const latestEvals: Record<string, LatestEvaluationItem> = {
      'doc-1': {
        document_id: 'doc-1',
        evaluation_id: 'eval-active-1',
        status: 'EVALUATING',
        submitted_at: '2026-08-21T10:00:00Z',
      },
    };

    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={latestEvals}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    expect(markup).toContain('Evaluating');
    expect(markup.match(/href="\/documents\/doc-1\/evaluation"/g)).toHaveLength(2);
    expect(markup).not.toContain('href="/evaluations/eval-active-1"');
    expect(markup).toContain('aria-label="View evaluation progress for Data Structures SLM"');
  });

  it('links title and right action to the workspace when an evaluation failed', () => {
    const latestEvals: Record<string, LatestEvaluationItem> = {
      'doc-1': {
        document_id: 'doc-1',
        evaluation_id: 'eval-fail-1',
        status: 'FAILED',
        submitted_at: '2026-08-21T09:00:00Z',
        error_message: 'Agent timeout',
      },
    };

    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={latestEvals}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    expect(markup).toContain('Evaluation Failed');
    expect(markup.match(/href="\/documents\/doc-1\/evaluation"/g)).toHaveLength(2);
    expect(markup).not.toContain('href="/evaluations/eval-fail-1"');
    expect(markup).toContain('aria-label="Inspect evaluation for Data Structures SLM"');
  });

  it('renders Checking Status when latest evaluation status is loading and never falsely Ready', () => {
    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={{}}
        latestEvalsState={{ isLoading: true }}
      />,
    );

    expect(markup).toContain('Checking Status');
    expect(markup).not.toContain('Ready to Evaluate');
    expect(markup).not.toContain('href="/documents/doc-1/evaluation"');
  });

  it('renders Status Unavailable when latest evaluation query fails', () => {
    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[0]]}
        flashId={null}
        latestEvalsByDocId={{}}
        latestEvalsState={{ isError: true }}
      />,
    );

    expect(markup).toContain('Status Unavailable');
    expect(markup).not.toContain('Ready to Evaluate');
  });

  it('renders disabled text without action links for Processing and Upload Failed documents', () => {
    const markup = renderToStaticMarkup(
      <DocumentTable
        documents={[sampleDocuments[1], sampleDocuments[2]]}
        flashId={null}
        latestEvalsState={{ isSuccess: true }}
      />,
    );

    expect(markup).toContain('Processing');
    expect(markup).toContain('Upload Failed');
    expect(markup).not.toContain('href="/documents/doc-2/evaluation"');
    expect(markup).not.toContain('href="/documents/doc-3/evaluation"');
  });

  it('renders scope="col" on skeleton headers as well', () => {
    const markup = renderToStaticMarkup(<DocumentTableSkeleton />);
    const thMatches = markup.match(/<th\b[^>]*>/g) || [];
    expect(thMatches.length).toBe(7);
    for (const th of thMatches) {
      expect(th).toContain('scope="col"');
    }
  });
});
