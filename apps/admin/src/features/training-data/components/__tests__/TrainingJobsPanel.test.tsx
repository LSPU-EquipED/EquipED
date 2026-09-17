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

  it('shows download and upload URLs after starting a job', () => {
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
    expect(screen.getByText(/https:\/\/example\.test\/download/)).toBeDefined();
    expect(screen.getByText(/https:\/\/example\.test\/upload/)).toBeDefined();
  });
});
