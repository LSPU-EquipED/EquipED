// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AgentReviewModal } from '../AgentReviewModal';
import { evaluationApi } from '../../../api/evaluation.api';
import type { CriterionScoreItem } from '../../../types';

vi.mock('../../../api/evaluation.api', () => ({
  evaluationApi: {
    submitCriterionFeedback: vi.fn().mockResolvedValue({}),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderModal(criteria: readonly CriterionScoreItem[], onClose = vi.fn()) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentReviewModal
        agentName="sme"
        evaluationId="eval-1"
        criteria={criteria}
        onClose={onClose}
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


describe('review draft protection', () => {
  it('confirms discarding changed item selections, but leaves untouched reviews immediately', async () => {
    const onClose = vi.fn();
    renderModal([criterionWithItems], onClose);
    expandItemsChecklist();
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).not.toHaveBeenCalled();
    expect(await screen.findByRole('dialog', { name: 'Discard unsaved changes?' })).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(evaluationApi.submitCriterionFeedback).not.toHaveBeenCalled();
  });
  it('does not ask for confirmation when no changes were made', () => {
    const onClose = vi.fn(); renderModal([criterionWithItems], onClose);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.queryByRole('dialog', { name: 'Discard unsaved changes?' })).toBeNull();
  });
});

describe('review save and focus behavior', () => {
  it('keeps a saved correction visible without submitting it again', async () => {
    const onClose = vi.fn();
    renderModal([{
      ...criterionWithItems,
      reviewer_correction: { action: 'EDIT', score: 2, justification: 'Saved correction.' },
    }], onClose);
    expect(screen.getByText('Edited')).toBeDefined();
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe('Saved correction.');
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(evaluationApi.submitCriterionFeedback).not.toHaveBeenCalled();
  });

  it('saves the changed score and trimmed justification for the displayed run and criterion', async () => {
    const onClose = vi.fn();
    renderModal([criterionWithItems], onClose);
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  Reviewer finding.  ' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledOnce();
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
      'eval-1', 'OP-01',
      { agent_name: 'sme', action: 'EDIT', score: 2, justification: 'Reviewer finding.' },
    );
  });

  it('blocks saving an empty justification without discarding the draft', () => {
    renderModal([criterionWithItems]);
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } });
    expect(screen.getByText('Justification cannot be empty.')).toBeDefined();
    expect((screen.getByRole('button', { name: /save changes/i }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    expect(evaluationApi.submitCriterionFeedback).not.toHaveBeenCalled();
  });

  it('sends only the criterion rejection when a changed item belongs to a flagged criterion', async () => {
    const onClose = vi.fn();
    renderModal([criterionWithItems], onClose);
    expandItemsChecklist();
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Flag as incorrect' }));
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledOnce();
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
      'eval-1', 'OP-01', { agent_name: 'sme', action: 'REJECT' },
    );
  });

  it('keeps an already rejected criterion locked and submits no repeat rejection', async () => {
    const onClose = vi.fn();
    renderModal([{
      ...criterionWithItems,
      reviewer_correction: { action: 'REJECT', score: null, justification: null },
    }], onClose);
    expect((screen.getByRole('button', { name: /already flagged as incorrect/i }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(evaluationApi.submitCriterionFeedback).not.toHaveBeenCalled();
  });

  it('keeps the draft after a failed save and allows retrying the same corrections', async () => {
    const submit = vi.mocked(evaluationApi.submitCriterionFeedback);
    submit.mockRejectedValueOnce(new Error('Unavailable'));
    const onClose = vi.fn();
    renderModal([criterionWithItems], onClose);
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    expect(await screen.findByText("Some corrections couldn't be saved. Please try again.")).toBeDefined();
    expect(onClose).not.toHaveBeenCalled();
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe(criterionWithItems.justification);
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(submit).toHaveBeenCalledTimes(2);
    expect(submit.mock.calls[1]).toEqual(submit.mock.calls[0]);
  });

  it('wraps focus within the review and restores the opener when unmounted', () => {
    const opener = document.createElement('button');
    document.body.append(opener);
    opener.focus();
    const { unmount } = renderModal([criterionWithItems]);
    const close = screen.getByRole('button', { name: 'Close review' });
    const save = screen.getByRole('button', { name: /save changes/i });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(save);
    fireEvent.keyDown(save, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});
