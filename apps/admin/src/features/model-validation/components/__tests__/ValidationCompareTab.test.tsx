// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
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
    fireEvent.click(screen.getByRole('button', { name: 'Adapter run' }));
    options = screen.getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toContain('SLM a1');
    expect(options[0].textContent).toContain('v7');
  });

  it('keeps Compare disabled until both runs are chosen, then shows the summary', () => {
    render(<ValidationCompareTab history={history()} />);
    const button = screen.getByRole('button', { name: 'Compare' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    choose('Base run', /SLM b1/);
    expect(button.disabled).toBe(true);
    choose('Adapter run', /SLM a1/);
    expect(button.disabled).toBe(false);
    expect(screen.queryByText('Mean error vs expected')).toBeNull();

    fireEvent.click(button);
    // base errors 1,0,2 -> 1.00 ; adapter errors 0,0,1 -> 0.33
    const table = screen.getByRole('table');
    expect(within(table).getByText('Mean error vs expected')).toBeDefined();
    expect(within(table).getByText('1.00')).toBeDefined();
    expect(within(table).getByText('0.33')).toBeDefined();
    expect(within(table).getByText('CLOSER')).toBeDefined();
    expect(within(table).getByText('1 of 3')).toBeDefined();
    expect(within(table).getByText('2 of 3')).toBeDefined();
    expect(
      screen.getByText(
        'The adapter got closer to the expected scores on 2 criteria, stayed the same on 1 and moved away on 0.',
      ),
    ).toBeDefined();
    expect(
      screen.getByText(/Closer to the expected scores means the model followed them/),
    ).toBeDefined();
  });

  it('skip chips change the numbers', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));

    fireEvent.click(screen.getByRole('button', { name: /A-03/ }));
    const table = screen.getByRole('table');
    // remaining: base errors 1,0 -> 0.50 ; adapter 0,0 -> 0.00
    expect(within(table).getByText('0.50')).toBeDefined();
    expect(within(table).getByText('0.00')).toBeDefined();
    expect(within(table).getByText('1 of 2')).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: /A-01/ }));
    fireEvent.click(screen.getByRole('button', { name: /A-02/ }));
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText(/skipped every criterion/i)).toBeDefined();
  });

  it('shows the different-copy note only when document ids differ', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText(/different uploaded copies/)).toBeDefined();
    cleanup();

    const same = [items[0], { ...items[1], document_id: 'doc-1' } as ModelValidationItem];
    render(<ValidationCompareTab history={historyOf(same)} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.queryByText(/different uploaded copies/)).toBeNull();
  });

  it('explains when the runs share no comparable criteria', () => {
    const lonely = [items[0], item('a3', 'adapter', [score('Z-09', 3, 3)])];
    render(<ValidationCompareTab history={historyOf(lonely)} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a3/);
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
      screen.getByText(/at least one completed base run and one completed adapter run/i),
    ).toBeDefined();
  });

  it('shows the winner banner and Better badges', () => {
    render(<ValidationCompareTab history={history()} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('Adapter is closer to the expected scores')).toBeDefined();
    const table = screen.getByRole('table');
    // mean error and exact matches both favour the adapter
    expect(within(table).getAllByText('Better')).toHaveLength(2);
    expect(within(table).getAllByLabelText('Adapter is better')).toHaveLength(2);
    expect(within(table).queryByLabelText('Base is better')).toBeNull();
  });

  it('shows Tie and no Better badge when the runs score the same', () => {
    const twin = [
      item('b1', 'base', [score('A-01', 3, 2)]),
      item('a1', 'adapter', [score('A-01', 3, 2)]),
    ];
    render(<ValidationCompareTab history={historyOf(twin)} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(screen.getByText('Tie')).toBeDefined();
    expect(screen.queryByText('Better')).toBeNull();
  });

  it('lists criteria skipped for differing expected scores without chips', () => {
    const list = [
      item('b1', 'base', [score('A-01', 3, 2), score('A-05', 3, 3)]),
      item('a1', 'adapter', [score('A-01', 3, 3), score('A-05', 4, 4)]),
    ];
    render(<ValidationCompareTab history={historyOf(list)} />);
    choose('Base run', /SLM b1/);
    choose('Adapter run', /SLM a1/);
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(
      screen.getByText('Skipped 1 criteria because the two runs have different expected scores: A-05'),
    ).toBeDefined();
    expect(screen.queryByRole('button', { name: /A-05/ })).toBeNull();
  });
});
