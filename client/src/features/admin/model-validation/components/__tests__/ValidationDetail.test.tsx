// @vitest-environment jsdom
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { HistoryRow, ValidationDetail } from '../ValidationDetail';
import type { ModelValidationItem } from '../../types';

// Mock the queries used inside ValidationDetail
vi.mock('../../hooks/useModelValidationQueries', () => ({
  useModelValidationDetail: () => ({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  }),
  useModelValidationEvaluation: () => ({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, ...props }: ComponentPropsWithoutRef<'a'> & { children?: ReactNode }) => (
    <a {...props}>{children}</a>
  ),
}));

afterEach(() => {
  cleanup();
});

const mockItem: ModelValidationItem = {
  validation_id: 'val-uuid-1',
  evaluation_id: 'eval-uuid-1',
  document_id: 'doc-uuid-1',
  document_title: 'Introduction to Computing SLM',
  partial_without_curriculum: true,
  bound_forms: [
    {
      agent_id: 'sme',
      rubric_set_id: 'set-sme-1',
      rubric_version: 1,
      adapter_key: 'sme_guidance_adapter',
      adapter_version: 1,
    },
    {
      agent_id: 'gad',
      rubric_set_id: 'set-gad-1',
      rubric_version: 2,
      adapter_key: 'gad_score_adapter',
      adapter_version: 2,
    },
    {
      agent_id: 'itso',
      rubric_set_id: 'set-itso-1',
      rubric_version: 1,
      adapter_key: 'itso_guidance_adapter',
      adapter_version: 1,
    },
  ],
  criterion_scores: [
    {
      expected_score_id: 'exp-1',
      agent_id: 'sme',
      rubric_set_id: 'set-sme-1',
      rubric_version: 1,
      rubric_criterion_id: 'crit-sme-1',
      criterion_id: 'SME_1',
      criterion_title: 'Content accuracy',
      expected_score: 4,
      actual_score: 4,
      absolute_error: 0,
    },
    {
      expected_score_id: 'exp-2',
      agent_id: 'gad',
      rubric_set_id: 'set-gad-1',
      rubric_version: 2,
      rubric_criterion_id: 'crit-gad-1',
      criterion_id: 'GAD_1',
      criterion_title: 'Gender sensitivity',
      expected_score: 3,
      actual_score: 2,
      absolute_error: 1,
    },
  ],
  absolute_error: 0.5,
  latency_seconds: 12.3,
  score_perplexity: 1.65,
  toxicity_score: 0.02,
  toxicity_label: 'Low',
  toxicity_explanation: 'No offensive language',
  toxicity_model: 'llama3',
  toxicity_error: null,
  status: 'COMPLETED',
  error_message: null,
  created_at: '2026-08-30T10:00:00Z',
};

describe('ValidationDetail', () => {
  it('renders bound rubric revisions panel with version, adapter, and rubric set id', () => {
    render(
      <ValidationDetail
        id="test-detail"
        validationId={mockItem.validation_id}
        evaluationId={mockItem.evaluation_id}
        fallbackCriteria={mockItem.criterion_scores}
        boundForms={mockItem.bound_forms}
        partialWithoutCurriculum={mockItem.partial_without_curriculum}
        overallStatus={mockItem.status}
        errorMessage={mockItem.error_message}
        isExpanded={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('Bound rubric revisions')).toBeDefined();
    expect(
      screen.getByText(/Immutable form snapshots bound at validation admission/i),
    ).toBeDefined();
    expect(screen.getAllByText('Rubric v1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Rubric v2').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/sme_guidance_adapter \(v1\)/i)).toBeDefined();
    expect(screen.getByText(/gad_score_adapter \(v2\)/i)).toBeDefined();
    expect(screen.getByText('set-sme-1')).toBeDefined();
    expect(screen.getByText('set-gad-1')).toBeDefined();
  });

  it('renders Coordinator as skipped in partial evaluation without curriculum', () => {
    render(
      <ValidationDetail
        id="test-detail"
        validationId={mockItem.validation_id}
        evaluationId={mockItem.evaluation_id}
        fallbackCriteria={mockItem.criterion_scores}
        boundForms={mockItem.bound_forms}
        partialWithoutCurriculum={true}
        overallStatus={mockItem.status}
        errorMessage={null}
        isExpanded={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/This validation ran without a curriculum reference/i)).toBeDefined();
  });
});

describe('HistoryRow', () => {
  it('renders bound form revision badges under the document title', () => {
    render(
      <table>
        <tbody>
          <HistoryRow
            item={mockItem}
            isExpanded={false}
            isAnyExpanded={false}
            comparedCount={2}
            exactMatches={1}
            onToggle={vi.fn()}
            onClose={vi.fn()}
          />
        </tbody>
      </table>,
    );

    expect(screen.getByText('Introduction to Computing SLM')).toBeDefined();
    expect(screen.getByText('SME v1')).toBeDefined();
    expect(screen.getByText('GAD v2')).toBeDefined();
    expect(screen.getByText('ITSO v1')).toBeDefined();
  });
});
