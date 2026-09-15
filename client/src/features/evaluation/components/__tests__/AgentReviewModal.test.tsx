// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AgentReviewModal } from '../AgentReviewModal';
import { evaluationApi } from '../../api/evaluation.api';
import type { CriterionScoreItem } from '../../types';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    submitCriterionFeedback: vi.fn().mockResolvedValue({}),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderModal(criteria: readonly CriterionScoreItem[]) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentReviewModal
        agentName="sme"
        evaluationId="eval-1"
        criteria={criteria}
        onClose={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

function expandItemsChecklist() {
  fireEvent.click(screen.getByRole('button', { name: /what counted toward this score/i }));
}

const criterionWithItems: CriterionScoreItem = {
  criterion_id: 'OP-01',
  criterion_text: 'Topic Coherence',
  score: 4,
  justification: 'Coverage evaluation: 2/2 qualifying units.',
  raw_items: [
    { item_id: 'u1', text: 'Unit 1 to Unit 2.', included: true, rejected: false },
    { item_id: 'u2', text: 'Unit 2 to Unit 3.', included: true, rejected: false },
  ],
  corrected_score: null,
};

describe('AgentReviewModal item-level correction', () => {
  it('collapses the checklist by default, showing only the disclosure button', () => {
    renderModal([criterionWithItems]);
    expect(screen.getByRole('button', { name: /what counted toward this score/i })).toBeDefined();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('expanding the disclosure reveals checked checkboxes matching raw_items', () => {
    renderModal([criterionWithItems]);
    expandItemsChecklist();

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0].checked).toBe(true);
    expect(checkboxes[1].checked).toBe(true);
  });

  it('unchecking an item and saving submits ITEM_REJECT for that item only', async () => {
    renderModal([criterionWithItems]);
    expandItemsChecklist();

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1].checked).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledTimes(1);
    });
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
      'eval-1',
      'OP-01',
      { agent_name: 'sme', action: 'ITEM_REJECT', item_id: 'u2' },
    );
  });

  it('re-checking a previously-rejected item submits ITEM_ACCEPT', async () => {
    const criterion: CriterionScoreItem = {
      ...criterionWithItems,
      raw_items: [
        { item_id: 'u1', text: 'Unit 1 to Unit 2.', included: true, rejected: false },
        { item_id: 'u2', text: 'Unit 2 to Unit 3.', included: true, rejected: true },
      ],
      corrected_score: 3,
    };
    renderModal([criterion]);
    expandItemsChecklist();

    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    expect(checkboxes[1].checked).toBe(false);
    fireEvent.click(checkboxes[1]);

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
        'eval-1',
        'OP-01',
        { agent_name: 'sme', action: 'ITEM_ACCEPT', item_id: 'u2' },
      );
    });
  });

  it('submits nothing when no item toggles or score edits are made', async () => {
    const onClose = vi.fn();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AgentReviewModal
          agentName="sme"
          evaluationId="eval-1"
          criteria={[criterionWithItems]}
          onClose={onClose}
        />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(evaluationApi.submitCriterionFeedback).not.toHaveBeenCalled();
  });

  it('shows the corrected-score hint on the collapsed disclosure button', () => {
    renderModal([{ ...criterionWithItems, corrected_score: 3 }]);
    expect(screen.getByText(/recalculates to 3\/4 on save/i)).toBeDefined();
  });

  it('explains the checklist in terms of the criterion name once expanded', () => {
    renderModal([criterionWithItems]);
    expandItemsChecklist();
    expect(
      screen.getByText(/these are the specific things the ai found while checking/i),
    ).toBeDefined();
  });

  it('renders no checklist disclosure for criteria without raw_items', () => {
    renderModal([{ ...criterionWithItems, raw_items: null }]);
    expect(
      screen.queryByRole('button', { name: /what counted toward this score/i }),
    ).toBeNull();
  });
});
