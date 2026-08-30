// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Scorecard } from '../Scorecard';
import { evaluationApi } from '../../api/evaluation.api';
import * as useEvaluationModule from '../../hooks/useEvaluationStatus';
import type { EvaluationResponse, EvaluationResultsResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ id: 'eval-123' }),
  Outlet: () => null,
}));

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    getEvaluationResults: vi.fn(),
  },
}));

vi.mock('../ScorecardPdfExport', () => ({
  ScorecardPdfExport: () => <button type="button">Export PDF Mock</button>,
}));

describe('Scorecard - Dynamic CID Forms & Ungrounded/Legacy Presentation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  function renderScorecard() {
    return render(
      <QueryClientProvider client={queryClient}>
        <Scorecard />
      </QueryClientProvider>,
    );
  }

  it('renders dynamic form revision identity and ordered dynamic criteria without fixed assumptions', async () => {
    vi.spyOn(useEvaluationModule, 'useEvaluation').mockReturnValue({
      data: {
        evaluation_id: 'eval-123',
        document_id: 'doc-456',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T10:00:00Z',
        completed_at: '2026-08-20T10:02:00Z',
        duration_seconds: 120,
      } as unknown as EvaluationResponse,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvaluationModule.useEvaluation>);

    const mockResults: EvaluationResultsResponse = {
      evaluation_id: 'eval-123',
      document_id: 'doc-456',
      document_title: 'Introduction to Computing SLM',
      program: 'BSCS',
      synthesized_score: 95,
      overall_score: 3.8,
      adjectival_rating: 'Very Satisfactory',
      active_agents: ['sme'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      domain_scores: {
        sme: {
          form_snapshot_id: 'snap-uuid-1',
          rubric_set_id: 'rubric-uuid-1',
          version: 2,
          adapter_key: 'sme_adapter_v1',
          adapter_version: 1,
          criteria: [
            {
              criterion_id: 'CID-CUSTOM-01',
              criterion_text: 'Dynamic Novel Criterion',
              description: 'A dynamically authored criterion description.',
              score: 4,
              justification: 'Exemplary execution.',
              evidence: 'Found on page 5.',
              is_ungrounded: false,
            },
          ],
          subtotal: 4,
          max_score: 4,
          status: 'OK',
          adjectival_rating: 'Very Satisfactory',
        },
      },
      flags: [],
    };

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue(mockResults);

    renderScorecard();

    await waitFor(() => {
      expect(screen.getByText(/Revision 2/i)).toBeDefined();
    });

    expect(screen.getByText('CID-CUSTOM-01')).toBeDefined();
    expect(screen.getByText('Dynamic Novel Criterion')).toBeDefined();
    expect(screen.getByText('A dynamically authored criterion description.')).toBeDefined();
    expect(screen.getByText(/Found on page 5/i)).toBeDefined();
    expect(screen.queryByText(/Legacy — form snapshot unavailable/i)).toBeNull();
  });

  it('renders explicit ungrounded status for criteria marked as ungrounded', async () => {
    vi.spyOn(useEvaluationModule, 'useEvaluation').mockReturnValue({
      data: {
        evaluation_id: 'eval-123',
        document_id: 'doc-456',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T10:00:00Z',
      } as unknown as EvaluationResponse,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvaluationModule.useEvaluation>);

    const mockResults: EvaluationResultsResponse = {
      evaluation_id: 'eval-123',
      document_id: 'doc-456',
      synthesized_score: 75,
      overall_score: 3.0,
      active_agents: ['itso'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      domain_scores: {
        itso: {
          version: 1,
          criteria: [
            {
              criterion_id: 'ITSO-NOVEL',
              criterion_text: 'Ungrounded Innovation Citation',
              score: 2,
              justification: 'Reference source could not be verified.',
              is_ungrounded: true,
            },
          ],
          subtotal: 2,
          max_score: 4,
          status: 'OK',
          adjectival_rating: 'Satisfactory',
        },
      },
      flags: [],
    };

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue(mockResults);

    renderScorecard();

    await waitFor(() => {
      expect(screen.getAllByText('Ungrounded').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('ITSO-NOVEL')).toBeDefined();
    expect(screen.getByText('Ungrounded Innovation Citation')).toBeDefined();
  });

  it('renders exact legacy notice without inventing a revision', async () => {
    vi.spyOn(useEvaluationModule, 'useEvaluation').mockReturnValue({
      data: {
        evaluation_id: 'eval-legacy-001',
        document_id: 'doc-456',
        status: 'COMPLETED',
        submitted_at: '2026-05-01T10:00:00Z',
      } as unknown as EvaluationResponse,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvaluationModule.useEvaluation>);

    const mockResults: EvaluationResultsResponse = {
      evaluation_id: 'eval-legacy-001',
      document_id: 'doc-456',
      synthesized_score: 80,
      overall_score: 3.2,
      active_agents: ['sme'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      legacy_notice: 'Legacy — form snapshot unavailable',
      domain_scores: {
        sme: {
          criteria: [
            {
              criterion_id: 'OP-01',
              criterion_text: 'Content Clarity',
              score: 3,
              justification: 'Clear structure.',
              is_ungrounded: false,
            },
          ],
          subtotal: 3,
          max_score: 4,
          status: 'OK',
        },
      },
      flags: [],
    };

    vi.mocked(evaluationApi.getEvaluationResults).mockResolvedValue(mockResults);

    renderScorecard();

    await waitFor(() => {
      const legacyNotices = screen.getAllByText('Legacy — form snapshot unavailable');
      expect(legacyNotices.length).toBeGreaterThanOrEqual(1);
    });

    // Must NEVER invent a revision like "Revision 1" or "Revision undefined"
    expect(screen.queryByText(/Revision/i)).toBeNull();
  });
});
