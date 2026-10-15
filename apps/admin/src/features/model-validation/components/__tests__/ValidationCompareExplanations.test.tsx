// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import type { ModelValidationItem } from '../../types';
import type { ButtonHTMLAttributes } from 'react';
import { compareChipKey } from '../../utils/compare';
import { ValidationCompareCriteria } from '../ValidationCompareCriteria';

const { detailQuery } = vi.hoisted(() => ({ detailQuery: vi.fn() }));
vi.mock('@phosphor-icons/react', () => ({ CaretDown: () => null }));
vi.mock('@equiped/ui', () => ({
  cn: (...values: unknown[]) => values.filter(Boolean).join(' '),
  Button: ({ children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props}>{children}</button>,
  Skeleton: () => <span>Loading</span>,
}));
vi.mock('../../hooks/useModelValidationQueries', () => ({
  useModelValidationDetail: detailQuery,
}));

const base = {
  validation_id: 'base-run', model_variant: 'base', adapter_label: null,
  criterion_scores: [{ agent_id: 'sme', criterion_id: 'OP-05', criterion_title: 'Enhancement Activities', expected_score: 1, actual_score: 3 }],
} as ModelValidationItem;
const adapter = { ...base, validation_id: 'adapter-run', model_variant: 'adapter', adapter_label: 'sme-v12' } as ModelValidationItem;

function detail(run: ModelValidationItem, explanation: Record<string, unknown> | null) {
  return { ...run, criterion_scores: [{ ...run.criterion_scores[0], explanation }] };
}

function show() {
  render(<ValidationCompareCriteria base={base} adapter={adapter}
    chips={[{ key: compareChipKey('sme', 'OP-05'), label: 'SME · OP-05', skipped: false }]}
    onToggle={vi.fn()} />);
  const summary = screen.getByText('Evidence and reasoning');
  const disclosure = summary.closest('details')!;
  disclosure.open = true;
  fireEvent(disclosure, new Event('toggle'));
}

beforeEach(() => {
  detailQuery.mockImplementation((id: string) => ({
    data: detail(id === base.validation_id ? base : adapter, {
      status: id === base.validation_id ? 'ok' : 'repaired', model_name: 'gemma-test',
      evidence: [id === base.validation_id ? 'Base exact quote' : 'Adapter exact quote'],
      reasoning: id === base.validation_id ? 'Base captured reasoning' : 'Adapter captured reasoning',
      stored_justification: null,
    }), isLoading: false, isError: false,
  }));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('criterion explanation comparison', () => {
  it('loads explanations only after opening and shows both captured responses and version', () => {
    render(<ValidationCompareCriteria base={base} adapter={adapter}
      chips={[{ key: compareChipKey('sme', 'OP-05'), label: 'SME · OP-05', skipped: false }]}
      onToggle={vi.fn()} />);
    expect(detailQuery).not.toHaveBeenCalled();
    const disclosure = screen.getByText('Evidence and reasoning').closest('details')!;
    disclosure.open = true;
    fireEvent(disclosure, new Event('toggle'));
    expect(screen.getByText('Base exact quote')).toBeDefined();
    expect(screen.getByText('Adapter exact quote')).toBeDefined();
    expect(screen.getByText('Base captured reasoning')).toBeDefined();
    expect(screen.getByText('Adapter captured reasoning')).toBeDefined();
    expect(screen.getByText('sme-v12')).toBeDefined();
    expect(screen.getByText('Repaired model response')).toBeDefined();
  });

  it('labels fallback justifications separately from model reasoning', () => {
    detailQuery.mockReturnValue({ data: detail(base, {
      status: 'fallback', evidence: ['Placeholder quote'], reasoning: null,
      stored_justification: 'Evaluation unverified: grounding failed', model_name: 'gemma-test',
    }), isLoading: false, isError: false });
    show();
    expect(screen.getAllByText(/Fallback placeholder/)).toHaveLength(2);
    expect(screen.getAllByText('Fallback justification')).toHaveLength(2);
    expect(screen.getAllByText('Evaluation unverified: grounding failed')).toHaveLength(2);
    expect(screen.queryByText('Base captured reasoning')).toBeNull();
  });

  it('shows missing reasoning and evidence explicitly, with legacy justification labelled', () => {
    detailQuery.mockReturnValue({ data: detail(base, {
      status: 'unavailable', evidence: null, reasoning: null,
      stored_justification: 'Legacy explanation', model_name: null,
    }), isLoading: false, isError: false });
    show();
    expect(screen.getAllByText('Reasoning not stored.')).toHaveLength(2);
    expect(screen.getAllByText('Evidence not stored.')).toHaveLength(2);
    expect(screen.getAllByText('Stored justification')).toHaveLength(2);
    expect(screen.getAllByText('Legacy explanation')).toHaveLength(2);
  });

  it('shows unavailable explanations rather than inventing historical data', () => {
    detailQuery.mockReturnValue({ data: detail(base, null), isLoading: false, isError: false });
    show();
    expect(screen.getAllByText('Reasoning not stored.')).toHaveLength(2);
    expect(screen.getAllByText('Evidence not stored.')).toHaveLength(2);
  });

  it('offers retry when explanation retrieval fails', () => {
    const refetch = vi.fn();
    detailQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch });
    show();
    const alerts = screen.getAllByRole('alert');
    expect(alerts).toHaveLength(2);
    fireEvent.click(within(alerts[0]).getByRole('button', { name: 'Try again' }));
    expect(refetch).toHaveBeenCalledOnce();
  });
});
