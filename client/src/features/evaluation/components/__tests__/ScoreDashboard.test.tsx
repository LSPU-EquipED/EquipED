// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ScoreDashboard } from '../ScoreDashboard';
import type { EvaluationResultsResponse, EvaluationStatusResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../ScorecardPdfExport', () => ({
  ScorecardPdfExport: () => <button type="button">Mock Export</button>,
}));

vi.mock('../FeedbackPanel', () => ({
  FeedbackPanel: () => <div data-testid="feedback-panel">Feedback Panel Mock</div>,
}));

describe('ScoreDashboard - Dynamic CID Forms & Ungrounded/Legacy Presentation', () => {
  afterEach(() => {
    cleanup();
  });

  function renderDashboard(props: Partial<Parameters<typeof ScoreDashboard>[0]> = {}) {
    const defaultProps = {
      status: {
        evaluation_id: 'eval-1',
        status: 'COMPLETED',
        completed_at: '2026-08-20T10:00:00Z',
      } as EvaluationStatusResponse,
      results: undefined as EvaluationResultsResponse | undefined,
      isTerminal: true,
      isInProgress: false,
      isFailedWithResults: false,
      isResultsError: false,
      resultsError: null,
      refetchResults: vi.fn(),
      handleRetryEvaluation: vi.fn(),
      isResolvingEval: false,
      submitIsPending: false,
      evaluationId: 'eval-1',
      selectedAgentId: 'sme' as const,
      onSelectAgent: vi.fn(),
      ...props,
    };
    return render(<ScoreDashboard {...defaultProps} />);
  }

  it('renders dynamic criteria with custom code, title, and description without fixed count assumptions', () => {
    const results: EvaluationResultsResponse = {
      evaluation_id: 'eval-1',
      document_id: 'doc-1',
      synthesized_score: 90,
      overall_score: 3.6,
      adjectival_rating: 'Very Satisfactory',
      active_agents: ['sme'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      domain_scores: {
        sme: {
          version: 4,
          form_snapshot_id: 'snap-4',
          subtotal: 4,
          max_score: 4,
          status: 'OK',
          criteria: [
            {
              criterion_id: 'SME-DYN-01',
              criterion_text: 'Dynamic Taxonomy Alignment',
              description: 'Checks Bloom taxonomy alignment dynamically.',
              score: 4,
              justification: 'Aligned across all modules.',
              is_ungrounded: false,
            },
          ],
        },
      },
      flags: [],
    };

    renderDashboard({ results, selectedAgentId: 'sme' });

    expect(screen.getByText(/Revision 4/i)).toBeDefined();
    expect(screen.getByText('SME-DYN-01')).toBeDefined();
    expect(screen.getByText('Dynamic Taxonomy Alignment')).toBeDefined();
    expect(screen.getByText('Checks Bloom taxonomy alignment dynamically.')).toBeDefined();
    expect(screen.queryByText(/Legacy — form snapshot unavailable/i)).toBeNull();
  });

  it('renders explicit ungrounded status in criteria table', () => {
    const results: EvaluationResultsResponse = {
      evaluation_id: 'eval-1',
      document_id: 'doc-1',
      synthesized_score: 60,
      overall_score: 2.4,
      active_agents: ['itso'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      domain_scores: {
        itso: {
          version: 1,
          form_snapshot_id: 'snap-itso',
          subtotal: 2,
          max_score: 4,
          status: 'OK',
          criteria: [
            {
              criterion_id: 'ITSO-09',
              criterion_text: 'Third-party License Grounding',
              score: 1,
              justification: 'Missing evidence.',
              is_ungrounded: true,
            },
          ],
        },
      },
      flags: [],
    };

    renderDashboard({ results, selectedAgentId: 'itso' });

    const ungroundedBadges = screen.getAllByText('Ungrounded');
    expect(ungroundedBadges.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('ITSO-09')).toBeDefined();
  });

  it('renders exact legacy notice without inventing a revision when legacy_notice is set', () => {
    const results: EvaluationResultsResponse = {
      evaluation_id: 'eval-1',
      document_id: 'doc-1',
      synthesized_score: 75,
      overall_score: 3.0,
      active_agents: ['gad'],
      failed_agents: [],
      is_partial: false,
      evaluation_status: 'COMPLETED',
      legacy_notice: 'Legacy — form snapshot unavailable',
      domain_scores: {
        gad: {
          subtotal: 3,
          max_score: 4,
          status: 'OK',
          criteria: [
            {
              criterion_id: 'GAD-01',
              criterion_text: 'Gender Sensitivity',
              score: 3,
              justification: 'Balanced representation.',
              is_ungrounded: false,
            },
          ],
        },
      },
      flags: [],
    };

    renderDashboard({ results, selectedAgentId: 'gad' });

    const notices = screen.getAllByText('Legacy — form snapshot unavailable');
    expect(notices.length).toBeGreaterThanOrEqual(1);
    // Must NOT invent a revision number
    expect(screen.queryByText(/Revision/i)).toBeNull();
  });
});
