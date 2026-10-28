// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UseQueryResult } from '@tanstack/react-query';
import { ValidationHistoryTable } from '../ValidationHistoryTable';
import type { ModelValidationItem, ModelValidationListResponse } from '../../types';
import { mockNativeDialog } from './nativeDialog';

vi.mock('../../hooks/useModelValidationQueries', () => ({
  useModelValidationDetail: () => ({ data: null, isLoading: false, isError: false }),
  useModelValidationEvaluation: () => ({ data: null, isLoading: false, isError: false }),
}));

let restoreDialog: () => void;
beforeAll(() => {
  restoreDialog = mockNativeDialog();
});
afterAll(() => restoreDialog());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

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
  it.each(['close button', 'backdrop', 'Escape'])(
    'opens review as a modal and restores the trigger after closing with %s',
    (method) => {
      vi.useFakeTimers();
      renderTable();
      const trigger = screen.getByRole('button', { name: 'Open evaluation for Algorithms SLM' });
      trigger.focus();
      fireEvent.click(trigger);
      act(() => {
        vi.advanceTimersByTime(16);
      });
      const dialog = screen.getByRole('dialog', { name: 'Validation details for Algorithms SLM' });
      expect((dialog as HTMLDialogElement).open).toBe(true);
      expect(trigger.getAttribute('aria-haspopup')).toBe('dialog');
      expect(trigger.getAttribute('aria-controls')).toBe(dialog.id);
      expect(document.body.style.overflow).toBe('hidden');
      const close = screen.getByRole('button', { name: 'Close validation details' });
      expect(document.activeElement).toBe(close);

      if (method === 'close button') fireEvent.click(close);
      else if (method === 'backdrop') fireEvent.click(dialog);
      else fireEvent(dialog, new Event('cancel', { cancelable: true }));

      expect(dialog.isConnected).toBe(true);
      act(() => {
        vi.advanceTimersByTime(240);
      });
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(trigger);
      expect(document.body.style.overflow).toBe('');
      expect(screen.getByText('Algorithms SLM')).toBeDefined();
    },
  );

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
