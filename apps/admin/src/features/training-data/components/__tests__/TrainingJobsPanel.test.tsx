// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { TrainingJobsPanel } from '../TrainingJobsPanel';
import * as useTrainingJobsModule from '../../hooks/useTrainingJobs';
import * as useStartTrainingJobModule from '../../hooks/useStartTrainingJob';
import type { TrainingJobCreateResponse, TrainingJobListResponse } from '../../types';

const emptyJobs: TrainingJobListResponse = { agent_id: 'gad', jobs: [] };

describe('TrainingJobsPanel', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: emptyJobs,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderPanel() {
    return render(
      <QueryClientProvider client={queryClient}>
        <TrainingJobsPanel agentId="gad" />
      </QueryClientProvider>,
    );
  }

  it('renders a Start Training Job button', () => {
    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    expect(screen.getByRole('button', { name: /start training job/i })).toBeDefined();
  });

  it('orchestrates starting a job and delegates credential rendering on success', () => {
    const result: TrainingJobCreateResponse = {
      job_id: 'job-1',
      agent_id: 'gad',
      status: 'pending',
      download_url: 'https://example.test/download?token=abc',
      upload_url: 'https://example.test/upload?token=def',
      download_expires_at: new Date().toISOString(),
      upload_expires_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    };

    const mutate = vi.fn(
      (_variables: unknown, options?: { onSuccess?: (data: TrainingJobCreateResponse) => void }) => {
        options?.onSuccess?.(result);
      },
    );

    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    const button = screen.getByRole('button', { name: /start training job/i });
    fireEvent.click(button);

    expect(mutate).toHaveBeenCalled();
    expect(
      screen.getByText(/Paste these into your Colab notebook now — each is shown only once\./),
    ).toBeDefined();
    expect(screen.getByText(/https:\/\/example\.test\/download/)).toBeDefined();
    expect(screen.getByText(/https:\/\/example\.test\/upload/)).toBeDefined();
  });

  it('renders mutation error message when job creation fails', () => {
    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error('Failed to reach server'),
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    expect(screen.getByText('Failed to reach server')).toBeDefined();
  });

  it('renders job history when jobs are returned', () => {
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: {
        agent_id: 'gad',
        jobs: [
          {
            job_id: 'job-abc-123',
            agent_id: 'gad',
            status: 'completed',
            created_at: '2026-03-01T10:00:00.000Z',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);

    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    expect(screen.getByText('job-abc-123')).toBeDefined();
    expect(screen.getByText('Completed')).toBeDefined();
  });

  it('shows what each job froze: pairs, evaluations and a short dataset hash', () => {
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: {
        agent_id: 'gad',
        jobs: [
          {
            job_id: 'job-frozen',
            agent_id: 'gad',
            status: 'pending',
            created_at: '2026-03-01T10:00:00.000Z',
            pair_count: 42,
            evaluation_count: 7,
            reviewer_count: 3,
            pairs_sha256: '0123456789abcdef',
            export_timestamp: '2026-03-01T10:00:00.000Z',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    expect(screen.getByText('42')).toBeDefined();
    expect(screen.getByText('7')).toBeDefined();
    expect(screen.getByText('01234567')).toBeDefined();
  });

  it('shows a dash for a job whose manifest recorded no counts', () => {
    vi.spyOn(useTrainingJobsModule, 'useTrainingJobs').mockReturnValue({
      data: {
        agent_id: 'gad',
        jobs: [
          {
            job_id: 'job-old',
            agent_id: 'gad',
            status: 'completed',
            created_at: '2026-03-01T10:00:00.000Z',
            pair_count: null,
            evaluation_count: null,
            reviewer_count: null,
            pairs_sha256: null,
            export_timestamp: null,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useTrainingJobsModule.useTrainingJobs>);
    vi.spyOn(useStartTrainingJobModule, 'useStartTrainingJob').mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useStartTrainingJobModule.useStartTrainingJob>);

    renderPanel();

    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
  });
});
