// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SpecialistScoreboardPage } from '../SpecialistScoreboardPage';
import { documentsApi } from '@/shared/api/documents.api';
import { evaluationApi } from '../../api/evaluation.api';
import type { ClientDocument } from '@/shared/types/documents';
import type { EvaluationListItem, EvaluationResultsResponse } from '../../types';
import type { TargetAgent } from '@/shared/types/evaluations';

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({}),
  useNavigate: () => vi.fn(),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

vi.mock('@/shared/api/documents.api', () => ({
  documentsApi: {
    listDocuments: vi.fn(),
    getCurriculumSuggestion: vi.fn(),
  },
}));

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    listEvaluations: vi.fn(),
    getEvaluationResults: vi.fn(),
  },
}));

const mockDoc: ClientDocument = {
  documentId: 'doc-slm-001',
  title: 'Data Structures SLM',
  courseTitle: 'Data Structures',
  lessonTitle: 'Module 1 - Arrays and Lists',
  academicYear: '2025-2026',
  courseCode: 'CS101',
  pageCount: 15,
  hasOcrPages: false,
  chunks: [],
  program: 'BSCS',
  sourceType: 'slm',
  uploadedAt: '2026-08-20T10:00:00Z',
  processingStatus: 'PROCESSED',
};

function renderPage(props: { agentId?: TargetAgent; documentId?: string } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SpecialistScoreboardPage {...props} />
    </QueryClientProvider>,
  );
}

describe('SpecialistScoreboardPage', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockReset();
    vi.mocked(evaluationApi.listEvaluations).mockReset();
    vi.mocked(evaluationApi.getEvaluationResults).mockReset();

    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [mockDoc],
      total: 1,
      page: 1,
      pageSize: 100,
    });

    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 5,
    });
  });

  it('renders specialist role header and empty state for unevaluated SLM', async () => {
    renderPage({ agentId: 'sme' });

    await waitFor(
      () => {
        expect(
          screen.getByRole('heading', {
            name: /No Subject Matter Expert \(SME\) Evaluation Yet/i,
          }),
        ).toBeDefined();
      },
      { timeout: 3000 },
    );

    expect(
      screen.getByRole('heading', {
        name: /Subject Matter Expert \(SME\) Review/i,
      }),
    ).toBeDefined();
    expect(screen.getAllByText(/SME Specialist/i)[0]).toBeDefined();
    expect(screen.getByRole('button', { name: /Evaluate as SME/i })).toBeDefined();
  });

  it('renders criterion scores when a completed evaluation exists for this specialist', async () => {
    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: 'eval-sme-1',
          document_id: 'doc-slm-001',
          status: 'COMPLETED',
          target_agent: 'sme',
          submitted_at: '2026-09-08T00:00:00Z',
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue({
      evaluation_id: 'eval-sme-1',
      document_id: 'doc-slm-001',
      evaluation_status: 'IN_PROGRESS',
      domain_scores: {
        sme: {
          subtotal: 3.5,
          max_score: 4,
          status: 'OK',
          adjectival_rating: 'Very Satisfactory',
          summary: 'Strong pedagogical structure and aligned content.',
          criteria: [
            {
              criterion_id: 'OP-01',
              criterion_text: 'Topic Coherence',
              score: 4,
              justification: 'Topics flow logically from basic to advanced structures.',
              evidence: 'Chapter 1 introduces basic linear arrays before moving to trees.',
            },
          ],
        },
      },
      flags: [],
    } as unknown as EvaluationResultsResponse);

    renderPage({ agentId: 'sme' });

    await waitFor(() => {
      expect(screen.getByText(/Subject Matter Expert \(SME\) Performance Score/i)).toBeDefined();
      expect(screen.getByText('Very Satisfactory')).toBeDefined();
      expect(screen.getByText('OP-01')).toBeDefined();
      expect(screen.getByText('Topic Coherence')).toBeDefined();
      expect(screen.getByText(/Chapter 1 introduces basic linear arrays/i)).toBeDefined();
    });
  });

  it('renders GAD review and GAD export button when agentId is gad', async () => {
    vi.mocked(evaluationApi.listEvaluations).mockResolvedValue({
      items: [
        {
          evaluation_id: 'eval-gad-1',
          document_id: 'doc-slm-001',
          status: 'COMPLETED',
          target_agent: 'gad',
          submitted_at: '2026-09-08T00:00:00Z',
        } as unknown as EvaluationListItem,
      ],
      total: 1,
      page: 1,
      page_size: 5,
    });

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue({
      evaluation_id: 'eval-gad-1',
      document_id: 'doc-slm-001',
      evaluation_status: 'IN_PROGRESS',
      domain_scores: {
        gad: {
          subtotal: 3.8,
          max_score: 4,
          status: 'OK',
          adjectival_rating: 'Very Satisfactory',
          criteria: [
            {
              criterion_id: 'GAD-01',
              criterion_text: 'Gender-Sensitive Language',
              score: 4,
              justification: 'Consistently uses gender-inclusive language and neutral pronouns.',
              evidence: 'The developer must ensure their implementation is verified.',
            },
          ],
        },
      },
      flags: [],
    } as unknown as EvaluationResultsResponse);

    renderPage({ agentId: 'gad' });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /GAD Unit Review/i })).toBeDefined();
      expect(screen.getAllByText(/GAD Specialist/i)[0]).toBeDefined();
      expect(screen.getByRole('button', { name: /Download PDF/i })).toBeDefined();
    });
  });
});
