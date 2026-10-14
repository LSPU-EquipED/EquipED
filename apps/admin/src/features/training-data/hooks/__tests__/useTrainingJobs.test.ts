// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { trainingDataApi } from '../../api/trainingData.api';
import { useTrainingJobs } from '../useTrainingJobs';
import { useHostSync } from '../useHostSync';

vi.mock('../../api/trainingData.api');
let client: QueryClient;

beforeEach(() => {
  vi.useFakeTimers();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  vi.mocked(trainingDataApi.listJobs).mockResolvedValue({
    agent_id: 'sme',
    jobs: [
      {
        job_id: 'j',
        agent_id: 'sme',
        status: 'pending',
        created_at: new Date().toISOString(),
      },
    ],
  });
  vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({
    has_active_key: true,
  });
});

afterEach(() => {
  cleanup();
  client.clear();
  focusManager.setFocused(undefined);
  vi.useRealTimers();
  vi.resetAllMocks();
});

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client }, children);
}

async function mountQueries() {
  const view = renderHook(() => ({ jobs: useTrainingJobs('sme'), host: useHostSync() }), {
    wrapper,
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(view.result.current.jobs.isSuccess).toBe(true);
  expect(view.result.current.host.isSuccess).toBe(true);
  return view;
}

describe('manual training-data refresh', () => {
  it('does not keep querying while a pending run is displayed', async () => {
    await mountQueries();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(65_000);
    });
    expect(trainingDataApi.listJobs).toHaveBeenCalledTimes(1);
    expect(trainingDataApi.getHostSync).toHaveBeenCalledTimes(1);
  });

  it('does not refetch when returning from Colab to the browser window', async () => {
    await mountQueries();
    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(trainingDataApi.listJobs).toHaveBeenCalledTimes(1);
    expect(trainingDataApi.getHostSync).toHaveBeenCalledTimes(1);
  });

  it('still supports explicit refresh', async () => {
    const view = await mountQueries();
    await act(async () => {
      await Promise.all([view.result.current.jobs.refetch(), view.result.current.host.refetch()]);
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(trainingDataApi.listJobs).toHaveBeenCalledTimes(2);
    expect(trainingDataApi.getHostSync).toHaveBeenCalledTimes(2);
  });
});
