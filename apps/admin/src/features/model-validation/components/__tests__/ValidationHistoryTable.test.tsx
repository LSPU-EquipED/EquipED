// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UseQueryResult } from '@tanstack/react-query';
import { ValidationHistoryTable } from '../ValidationHistoryTable';
import type { ModelValidationItem, ModelValidationListResponse } from '../../types';

afterEach(cleanup);

const item: ModelValidationItem = {
  validation_id: 'val-1',
  evaluation_id: 'eval-1',
  document_id: 'doc-1',
  document_title: 'Algorithms SLM',
  model_variant: null,
  adapter_id: null,
  adapter_label: null,
  adapter_resolution: null,
  compare_group_id: null,
  partial_without_curriculum: false,
  bound_forms: [],
  criterion_scores: [],
  absolute_error: null,
  latency_seconds: null,
  score_perplexity: null,
  toxicity_score: null,
  toxicity_label: null,
  toxicity_explanation: null,
  toxicity_model: null,
  toxicity_error: null,
  status: 'COMPLETED',
  error_message: null,
  created_at: '2026-09-01T10:00:00Z',
};

function renderTable(onRerun?: (i: ModelValidationItem) => void) {
  const history = {
    data: { items: [item], total: 1 },
    isLoading: false,
    isError: false,
  } as unknown as UseQueryResult<ModelValidationListResponse>;
  return render(<ValidationHistoryTable history={history} onRerun={onRerun} />);
}

describe('ValidationHistoryTable re-run', () => {
  it('calls onRerun with the row item', () => {
    const onRerun = vi.fn();
    renderTable(onRerun);
    fireEvent.click(screen.getByRole('button', { name: 'Re-run Algorithms SLM' }));
    expect(onRerun).toHaveBeenCalledWith(item);
  });

  it('shows no Re-run button without a handler', () => {
    renderTable();
    expect(screen.queryByRole('button', { name: /Re-run/ })).toBeNull();
  });
});
