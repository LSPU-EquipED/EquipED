// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { DatasetReadinessCard } from '../DatasetReadinessCard';
import * as useDatasetReadinessModule from '../../hooks/useDatasetReadiness';
import * as useTrainingJobsModule from '../../hooks/useTrainingJobs';
import type { DatasetReadiness, TrainingJobItem } from '../../types';

const readiness: DatasetReadiness = {
  agent_id: 'sme',
  pair_count: 31,
  evaluation_count: 6,
  reviewer_count: 2,
  skipped_counts: { no_reviewer_feedback: 9 },
  pairs_sha256: 'bbbbbbbbbbbbbbbb',
  export_timestamp: '2026-09-24T10:00:00.000Z',
};

function job(overrides: Partial<TrainingJobItem>): TrainingJobItem {
  return {
    job_id: 'job-1',
    agent_id: 'sme',
    status: 'pending',
    created_at: '2026-09-20T10:00:00.000Z',
    pair_count: 25,
    evaluation_count: 5,
    reviewer_count: 2,
    pairs_sha256: 'aaaaaaaaaaaaaaaa',
    export_timestamp: '2026-09-20T10:00:00.000Z',
    ...overrides,
  };
}

describe('DatasetReadinessCard', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: { agent_id: 'sme', jobs: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function mockReadiness(
    value: Partial<ReturnType<typeof useDatasetReadinessModule.useDatasetReadiness>>,
  ) {
    vi.spyOn(useDatasetReadinessModule, 'useDatasetReadiness').mockReturnValue(
      value as unknown as ReturnType<typeof useDatasetReadinessModule.useDatasetReadiness>,
    );
  }

  function renderCard(props: Partial<React.ComponentProps<typeof DatasetReadinessCard>> = {}) {
    return render(
      <QueryClientProvider client={queryClient}>
        <DatasetReadinessCard
          agentId="sme"
          onPrepare={vi.fn()}
          isPreparing={false}
          hasHandoff={false}
          preparationError={null}
          {...props}
        />
      </QueryClientProvider>,
    );
  }

  it('shows a loading state that is announced and keeps the card layout', () => {
    mockReadiness({ data: undefined, isLoading: true, isError: false });
    const { container } = renderCard();
    expect(screen.getByRole('status').textContent).toMatch(/checking dataset/i);
    expect(container.querySelectorAll('.skeleton-shimmer').length).toBeGreaterThan(0);
  });

  it('shows an announced error state that says how to recover', () => {
    mockReadiness({ data: undefined, isLoading: false, isError: true });
    renderCard();
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toMatch(/failed to check dataset readiness/i);
    expect(screen.getByRole('button', { name: /retry readiness/i })).toBeDefined();
  });

  it('shows counts, the funnel, and the skip reason', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard();

    expect(screen.getByText('31')).toBeDefined();
    expect(screen.getByText('6')).toBeDefined();
    expect(
      screen.getByText(
        '40 generations examined: 31 became pairs, 9 skipped (no reviewer feedback).',
      ),
    ).toBeDefined();
    expect(screen.getByText(/enough to try/i)).toBeDefined();
  });

  it('does not use the success color for the top tier, since nothing has validated it', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    const { container } = renderCard();
    expect(container.querySelector('.bg-success-soft')).toBeNull();
  });

  it('puts the seeded-data note above the verdict, not below it', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard();
    const note = screen.getByText(/seeded test data/i);
    const verdict = screen.getByText(/enough volume to attempt/i);
    expect(note.compareDocumentPosition(verdict) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('keeps inclusion details available in a disclosure', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard();
    const summary = screen.getByText('Dataset inclusion details');
    expect(summary.closest('details')?.open).toBe(false);
    expect(summary.closest('details')?.textContent).toMatch(/40 generations examined/);
  });

  it.each([
    { data: undefined, isLoading: true, isError: false },
    { data: undefined, isLoading: false, isError: true },
    { data: { ...readiness, pair_count: 0 }, isLoading: false, isError: false },
  ] as const)('prevents preparing a run with unavailable or empty data', (query) => {
    mockReadiness(query);
    const prepare = vi.fn();
    renderCard({ onPrepare: prepare });
    const button = screen.getByRole('button', {
      name: 'Prepare training run',
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(prepare).not.toHaveBeenCalled();
  });

  it('allows a small non-empty dataset while retaining its caveat', () => {
    mockReadiness({ data: { ...readiness, pair_count: 2 }, isLoading: false, isError: false });
    const prepare = vi.fn();
    renderCard({ onPrepare: prepare });
    fireEvent.click(screen.getByRole('button', { name: 'Prepare training run' }));
    expect(prepare).toHaveBeenCalledOnce();
    expect(screen.getByText(/smoke test/i)).toBeDefined();
  });

  it('prevents replacing unsaved notebook credentials', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard({ hasHandoff: true });
    expect(
      (screen.getByRole('button', { name: 'Prepare training run' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.getByText(/save the notebook URLs below/i)).toBeDefined();
  });

  it('warns when every correction comes from a single reviewer', () => {
    mockReadiness({
      data: { ...readiness, reviewer_count: 1 },
      isLoading: false,
      isError: false,
    });
    renderCard();
    expect(screen.getByText(/one reviewer/i)).toBeDefined();
  });

  it('does not show the single-reviewer note with several reviewers', () => {
    mockReadiness({
      data: { ...readiness, reviewer_count: 3 },
      isLoading: false,
      isError: false,
    });
    renderCard();
    expect(screen.queryByText(/one reviewer/i)).toBeNull();
  });

  it('shows the rule of thumb once for small and reasonable datasets only', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard();
    expect(screen.getAllByText(/rule of thumb/i)).toHaveLength(1);
    cleanup();

    mockReadiness({
      data: { ...readiness, pair_count: 0, evaluation_count: 0, skipped_counts: {} },
      isLoading: false,
      isError: false,
    });
    renderCard();
    expect(screen.queryByText(/rule of thumb/i)).toBeNull();
  });

  it('warns when only one evaluation is represented', () => {
    mockReadiness({
      data: { ...readiness, evaluation_count: 1 },
      isLoading: false,
      isError: false,
    });
    renderCard();
    expect(screen.getByText(/nothing can be held out/i)).toBeDefined();
  });

  it('always carries the seeded-test-data caveat', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    renderCard();
    expect(screen.getByText(/seeded test data/i)).toBeDefined();
  });

  it('says the dataset is identical to the latest job when the hash matches', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: {
        agent_id: 'sme',
        jobs: [job({ pair_count: 31, pairs_sha256: 'bbbbbbbbbbbbbbbb' })],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
    renderCard();
    expect(screen.getByText(/unchanged since the latest run/i)).toBeDefined();
    expect(screen.getByText(/preparing again uses the same data/i)).toBeDefined();
  });

  it('shows the count change against the latest job when the dataset differs', () => {
    mockReadiness({ data: readiness, isLoading: false, isError: false });
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: { agent_id: 'sme', jobs: [job({})] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
    renderCard();
    expect(screen.getByText(/25 → 31 pairs/)).toBeDefined();
  });
});
