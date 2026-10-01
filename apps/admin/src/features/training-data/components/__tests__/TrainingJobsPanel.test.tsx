// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { TrainingJobsPanel } from '../TrainingJobsPanel';
import { useTrainingJobs } from '../../hooks/useTrainingJobs';
import type { TrainingJobItem } from '../../types';

vi.mock('../../hooks/useTrainingJobs');
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const job: TrainingJobItem = {
  job_id: 'job-frozen',
  agent_id: 'sme',
  status: 'completed',
  created_at: '2026-03-01T10:00:00Z',
  pair_count: 42,
  evaluation_count: 7,
  reviewer_count: 3,
  pairs_sha256: '0123456789abcdef',
};

function renderJobs(jobs: TrainingJobItem[]) {
  vi.mocked(useTrainingJobs).mockReturnValue({
    data: { agent_id: 'sme', jobs },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useTrainingJobs>);
  return render(<TrainingJobsPanel agentId="sme" />);
}

describe('TrainingJobsPanel', () => {
  it('shows a compact empty history', () => {
    renderJobs([]);
    expect(screen.getByText(/no training runs yet/i)).toBeDefined();
    expect(screen.queryByRole('button', { name: /start training/i })).toBeNull();
  });

  it('summarizes the snapshot and describes completion as adapter receipt', () => {
    renderJobs([job]);
    expect(screen.getByText('42 pairs')).toBeDefined();
    expect(screen.getByText('7 evaluations')).toBeDefined();
    expect(screen.getByText('Adapter received')).toBeDefined();
    expect(screen.queryByText('Validated')).toBeNull();
  });

  it('expands full provenance without truncating its identifiers', () => {
    renderJobs([job]);
    const toggle = screen.getByRole('button', { name: /show details/i });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText(job.job_id)).toBeDefined();
    expect(screen.getByText(job.pairs_sha256!)).toBeDefined();
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
  });

  it('does not present missing historical counts as zero', () => {
    renderJobs([{ ...job, pair_count: null, evaluation_count: null, pairs_sha256: null }]);
    expect(screen.getByText('— pairs')).toBeDefined();
    expect(screen.getByText('— evaluations')).toBeDefined();
  });

  it('paginates run history and keeps the displayed run details available', () => {
    const jobs = Array.from({ length: 12 }, (_, index) => ({
      ...job,
      job_id: `run-${index + 1}`,
      pair_count: index + 1,
    }));
    renderJobs(jobs);
    const pagination = screen.getByRole('navigation', { name: 'Run history pagination' });
    expect(screen.getAllByRole('button', { name: /show details/i })).toHaveLength(5);
    expect(within(pagination).getByText('1–5 of 12')).toBeDefined();
    expect(
      (within(pagination).getByRole('button', { name: 'Previous' }) as HTMLButtonElement).disabled,
    ).toBe(true);

    fireEvent.click(within(pagination).getByRole('button', { name: 'Next' }));
    expect(screen.queryByText('1 pairs')).toBeNull();
    expect(screen.getByText('6 pairs')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Show details for run run-6' }));
    expect(screen.getByText('run-6')).toBeDefined();

    fireEvent.click(within(pagination).getByRole('button', { name: 'Next' }));
    expect(screen.getAllByRole('button', { name: /show details/i })).toHaveLength(2);
    expect(within(pagination).getByText('11–12 of 12')).toBeDefined();
    expect(
      (within(pagination).getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    fireEvent.click(within(pagination).getByRole('button', { name: 'Previous' }));
    expect(screen.getByText('6 pairs')).toBeDefined();
  });

  it('resets to the first page when selecting a different row count', () => {
    renderJobs(Array.from({ length: 12 }, (_, index) => ({ ...job, job_id: `run-${index}` })));
    const pagination = screen.getByRole('navigation', { name: 'Run history pagination' });
    fireEvent.click(within(pagination).getByRole('button', { name: 'Next' }));
    fireEvent.click(screen.getByRole('button', { name: 'Run history rows per page' }));
    fireEvent.click(screen.getByRole('option', { name: '10' }));
    expect(screen.getAllByRole('button', { name: /show details/i })).toHaveLength(10);
    expect(within(pagination).getByText('1–10 of 12')).toBeDefined();
    expect(screen.getByText('Page 1 / 2')).toBeDefined();
  });

  it('omits pagination for a short history', () => {
    renderJobs([job]);
    expect(screen.queryByRole('navigation', { name: 'Run history pagination' })).toBeNull();
  });
});
