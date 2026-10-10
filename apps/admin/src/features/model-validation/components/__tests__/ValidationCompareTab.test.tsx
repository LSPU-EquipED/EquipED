// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import type { UseQueryResult } from '@tanstack/react-query';
import type {
  ModelValidationCriterionScore,
  ModelValidationItem,
  ModelValidationListResponse,
} from '../../types';
import { ValidationCompareTab } from '../ValidationCompareTab';

function score(
  criterion: string,
  expected: number,
  actual: number | null,
): ModelValidationCriterionScore {
  return {
    expected_score_id: criterion,
    agent_id: 'sme',
    criterion_id: criterion,
    criterion_title: criterion,
    expected_score: expected,
    actual_score: actual,
    absolute_error: null,
  };
}

function item(
  id: string,
  variant: 'base' | 'adapter' | null,
  scores: ModelValidationCriterionScore[],
  extra: Partial<ModelValidationItem> = {},
): ModelValidationItem {
  return {
    validation_id: id,
    document_id: 'doc-1',
    document_title: `SLM ${id}`,
    model_variant: variant,
    adapter_label: variant === 'adapter' ? 'v7' : null,
    status: 'COMPLETED',
    created_at: '2026-09-01T10:00:00Z',
    criterion_scores: scores,
    ...extra,
  } as unknown as ModelValidationItem;
}

const items = [
  item('b1', 'base', [score('A-01', 3, 2), score('A-02', 3, 3), score('A-03', 3, 1)]),
  item('a1', 'adapter', [score('A-01', 3, 3), score('A-02', 3, 3), score('A-03', 3, 2)], {
    document_id: 'doc-2',
  }),
  item('b2', 'base', [], { status: 'FAILED' }),
  item('a2', 'adapter', [], { status: 'EVALUATING' }),
  item('n1', null, []),
];

function history(
  overrides: Partial<UseQueryResult<ModelValidationListResponse>> = {},
): UseQueryResult<ModelValidationListResponse> {
  return {
    data: { items, total: items.length },
    isLoading: false,
    isError: false,
    ...overrides,
  } as unknown as UseQueryResult<ModelValidationListResponse>;
}

function historyOf(list: ModelValidationItem[]) {
  return history({ data: { items: list, total: list.length } });
}

function choose(dropdownName: string, optionText: RegExp) {
  fireEvent.click(screen.getByRole('button', { name: dropdownName }));
  fireEvent.click(screen.getByRole('option', { name: optionText }));
}

afterEach(cleanup);

describe('ValidationCompareTab', () => {
  it('lists only completed runs of the right variant in each dropdown', () => {
    render(<ValidationCompareTab history={history()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Base run' }));
    let options = screen.getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toContain('SLM b1');
    expect(options[0].textContent).toContain('Base');
    cleanup();

    render(<ValidationCompareTab history={history()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Fine-tuned run' }));
    options = screen.getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toContain('SLM a1');
    expect(options[0].textContent).toContain('v7');
  });

  it('keeps Compare disabled until both runs are chosen, then shows the summary', () => {
    render(<ValidationCompareTab history={history()} />);
    const button = screen.getByRole('button', {
      name: 'Compare',
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    choose('Base run', /SLM b1/);
    expect(button.disabled).toBe(true);
    choose('Fine-tuned run', /SLM a1/);
    expect(button.disabled).toBe(false);
    expect(screen.queryByText('Mean error vs expected')).toBeNull();

    fireEvent.click(button);
    // base errors 1,0,2 -> 1.00 ; adapter errors 0,0,1 -> 0.33
    const table = screen.getByRole('table');
    expect(within(table).getByText('Mean error vs expected')).toBeDefined();
    expect(within(table).getByText('1.00')).toBeDefined();
    expect(within(table).getByText('0.33')).toBeDefined();
    expect(within(table).getByText('0.67 closer')).toBeDefined();
    expect(within(table).getByText('1 of 3')).toBeDefined();
    expect(within(table).getByText('2 of 3')).toBeDefined();
    expect(screen.getByLabelText('Fine-tuned model criterion changes')).toBeDefined();
    expect(screen.getByLabelText('Mean absolute error comparison')).toBeDefined();
    expect(screen.getByText('Lower is better')).toBeDefined();
    expect(
      screen.getByText(/Agreement with human reviewers depends on who supplied them/),
    ).toBeDefined();
  });

  it('criterion inclusion updates the numbers and can exclude every criterion', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));

    fireEvent.click(screen.getByText('Criterion details'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Include SME A-03' }));
    const table = screen.getByRole('table');
    // remaining: base errors 1,0 -> 0.50 ; adapter 0,0 -> 0.00
    expect(within(table).getByText('0.50')).toBeDefined();
    expect(within(table).getByText('0.00')).toBeDefined();
    expect(within(table).getByText('1 of 2')).toBeDefined();

    fireEvent.click(screen.getByRole('checkbox', { name: 'Include SME A-01' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Include SME A-02' }));
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText(/excluded every criterion/i)).toBeDefined();
  });

  it('shows the different-copy note only when document ids differ', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText(/different uploaded copies/)).toBeDefined();
    cleanup();

    const same = [items[0], { ...items[1], document_id: 'doc-1' } as ModelValidationItem];
    render(<ValidationCompareTab history={historyOf(same)} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.queryByText(/different uploaded copies/)).toBeNull();
  });

  it('explains when the runs share no comparable criteria', () => {
    const lonely = [items[0], item('a3', 'adapter', [score('Z-09', 3, 3)])];
    render(<ValidationCompareTab history={historyOf(lonely)} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a3/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText(/no criteria in common/i)).toBeDefined();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows loading and error states', () => {
    render(<ValidationCompareTab history={history({ isLoading: true, data: undefined })} />);
    expect(screen.getByRole('status', { name: 'Loading validation history' })).toBeDefined();
    cleanup();
    render(<ValidationCompareTab history={history({ isError: true, data: undefined })} />);
    expect(screen.getByText('Unable to load validation history.')).toBeDefined();
  });

  it('says so when there are no completed runs of a kind', () => {
    render(<ValidationCompareTab history={historyOf([])} />);
    expect(
      screen.getByText(/at least one completed base run and one completed fine-tuned run/i),
    ).toBeDefined();
  });

  it('shows one outcome without repeated winner badges', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('Fine-tuned model is closer to the expected scores')).toBeDefined();
    const table = screen.getByRole('table');
    expect(within(table).queryByText('Better')).toBeNull();
    expect(within(table).getByRole('columnheader', { name: 'Change' })).toBeDefined();
    expect(within(table).queryByText('Criteria: closer / same / farther')).toBeNull();
  });

  it('shows a tied outcome when the runs score the same', () => {
    const twin = [
      item('b1', 'base', [score('A-01', 3, 2)]),
      item('a1', 'adapter', [score('A-01', 3, 2)]),
    ];
    render(<ValidationCompareTab history={historyOf(twin)} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('The runs are tied')).toBeDefined();
    expect(screen.queryByText('Better')).toBeNull();
  });

  it('keeps expected-score mismatch exclusions visible and unavailable for inclusion', () => {
    const list = [
      item('b1', 'base', [score('A-01', 3, 2), score('A-05', 3, 3)]),
      item('a1', 'adapter', [score('A-01', 3, 3), score('A-05', 4, 4)]),
    ];
    render(<ValidationCompareTab history={historyOf(list)} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('1 criterion excluded: expected scores differ (A-05).')).toBeDefined();
    expect(screen.queryByRole('checkbox', { name: /A-05/ })).toBeNull();
  });

  it('hides the previous results after changing a run, and resets exclusions when comparing again', () => {
    const nextBase = item('b3', 'base', [
      score('A-01', 3, 3),
      score('A-02', 3, 3),
      score('A-03', 3, 3),
    ]);
    render(<ValidationCompareTab history={historyOf([...items, nextBase])} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    fireEvent.click(screen.getByText('Criterion details'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Include SME A-03' }));

    choose('Base run', /SLM b3/);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByText('Criterion details')).toBeNull();
    expect(screen.getByRole('status').textContent).toContain('Selections changed');

    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('Base is closer to the expected scores')).toBeDefined();
    fireEvent.click(screen.getByText('Criterion details'));
    expect(
      (
        screen.getByRole('checkbox', {
          name: 'Include SME A-03',
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(screen.getByText('3 of 3 included')).toBeDefined();
  });

  it('shows criterion titles and both predictions in the inclusion disclosure', () => {
    const titledBase = {
      ...items[0],
      criterion_scores: [{ ...score('A-01', 3, 2), criterion_title: 'Topic coherence' }],
    };
    render(<ValidationCompareTab history={historyOf([titledBase, items[1]])} />);
    choose('Base run', /SLM b1/);
    choose('Fine-tuned run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    fireEvent.click(screen.getByText('Criterion details'));
    expect(screen.getByText('Topic coherence')).toBeDefined();
    expect(
      (
        screen.getByRole('checkbox', {
          name: 'Include SME A-01',
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(screen.getByText('1 of 1 included')).toBeDefined();
  });

  it('offers retry and a direct action to prepare a missing benchmark', () => {
    const refetch = vi.fn().mockResolvedValue({});
    render(<ValidationCompareTab history={history({ isError: true, refetch })} />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(refetch).toHaveBeenCalledOnce();
    cleanup();
    const onNewBenchmark = vi.fn();
    render(<ValidationCompareTab history={historyOf([])} onNewBenchmark={onNewBenchmark} />);
    fireEvent.click(screen.getByRole('button', { name: 'New benchmark' }));
    expect(onNewBenchmark).toHaveBeenCalledOnce();
  });
});
