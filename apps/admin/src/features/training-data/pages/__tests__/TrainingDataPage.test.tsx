// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TrainingDataPage } from '../TrainingDataPage';
import { trainingDataApi } from '../../api/trainingData.api';
import type { TrainingJobCreateResponse } from '../../types';

const route = vi.hoisted(() => ({ agentId: 'coordinator', navigate: vi.fn() }));
vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ agentId: route.agentId }),
  useNavigate: () => route.navigate,
}));
vi.mock('../../api/trainingData.api');

const credentials: TrainingJobCreateResponse = {
  job_id: 'job-coordinator',
  agent_id: 'coordinator',
  status: 'pending',
  download_url: 'https://example.test/download?token=test',
  upload_url: 'https://example.test/upload?token=test',
  download_expires_at: '2099-01-01T00:00:00Z',
  upload_expires_at: '2099-01-01T00:00:00Z',
  created_at: '2026-09-29T00:00:00Z',
};

let client: QueryClient;
beforeEach(() => {
  route.agentId = 'coordinator';
  client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  route.navigate.mockImplementation(({ params }: { params: { agentId: string } }) => {
    route.agentId = params.agentId;
  });
  vi.mocked(trainingDataApi.getReadiness).mockImplementation(async (agentId) => ({
    agent_id: agentId,
    pair_count: 31,
    evaluation_count: 6,
    reviewer_count: 2,
    skipped_counts: {},
    pairs_sha256: 'hash',
    export_timestamp: '2026-09-29T00:00:00Z',
  }));
  vi.mocked(trainingDataApi.listJobs).mockImplementation(async (agentId) => ({
    agent_id: agentId,
    jobs: [],
  }));
  vi.mocked(trainingDataApi.listAdapters).mockImplementation(async (agentId) => ({
    agent_id: agentId,
    adapters: [],
    published_adapter_id: null,
    server_reachable: true,
    unrecognized_server_adapters: [],
  }));
});
afterEach(() => {
  cleanup();
  client.clear();
  vi.resetAllMocks();
});

function renderPage() {
  const content = (
    <QueryClientProvider client={client}>
      <TrainingDataPage />
    </QueryClientProvider>
  );
  const view = render(content);
  return {
    ...view,
    refreshRoute: () =>
      view.rerender(
        <QueryClientProvider client={client}>
          <TrainingDataPage />
        </QueryClientProvider>,
      ),
  };
}

async function prepareRun() {
  await waitFor(() =>
    expect(
      (screen.getByRole('button', { name: 'Prepare training run' }) as HTMLButtonElement).disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Prepare training run' }));
}

describe('TrainingDataPage', () => {
  it('supports keyboard navigation with matching selected tabs and panels', () => {
    const view = renderPage();
    const coordinator = screen.getByRole('tab', { name: 'Program Coordinator' });
    fireEvent.keyDown(coordinator, { key: 'ArrowRight' });
    view.refreshRoute();
    const sme = screen.getByRole('tab', { name: 'Subject Matter Expert' });
    expect(document.activeElement).toBe(sme);
    expect(sme.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(sme.id);
    fireEvent.keyDown(sme, { key: 'End' });
    view.refreshRoute();
    expect(
      screen
        .getByRole('tab', { name: 'Innovation and Technology Support Office' })
        .getAttribute('aria-selected'),
    ).toBe('true');
  });

  it('retains the correct specialist handoff when switching during a pending request', async () => {
    let resolveJob!: (value: TrainingJobCreateResponse) => void;
    vi.mocked(trainingDataApi.startJob).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveJob = resolve;
        }),
    );
    const view = renderPage();
    await prepareRun();
    await waitFor(() => expect(trainingDataApi.startJob).toHaveBeenCalledWith('coordinator'));
    fireEvent.click(screen.getByRole('tab', { name: 'Subject Matter Expert' }));
    view.refreshRoute();
    expect(
      (screen.getByRole('button', { name: 'Preparing run…' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    await act(async () => resolveJob(credentials));
    expect(screen.queryByLabelText('Download URL')).toBeNull();
    fireEvent.click(screen.getByRole('tab', { name: 'Program Coordinator' }));
    view.refreshRoute();
    expect(((await screen.findByLabelText('Download URL')) as HTMLInputElement).value).toBe(
      credentials.download_url,
    );
    expect(
      (screen.getByRole('button', { name: 'Prepare training run' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /saved both URLs/i }));
    expect(screen.queryByLabelText('Download URL')).toBeNull();
    expect(
      (screen.getByRole('button', { name: 'Prepare training run' }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(trainingDataApi.listJobs).toHaveBeenCalledWith('coordinator');
  });

  it('reports preparation failures and permits a retry', async () => {
    vi.mocked(trainingDataApi.startJob).mockRejectedValue(
      new Error('No eligible preference pairs remain.'),
    );
    renderPage();
    await prepareRun();
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain(
        'No eligible preference pairs remain.',
      ),
    );
    expect(
      (screen.getByRole('button', { name: 'Prepare training run' }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(screen.queryByLabelText('Download URL')).toBeNull();
  });
});
