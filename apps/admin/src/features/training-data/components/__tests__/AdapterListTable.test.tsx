// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AdapterListTable } from '../AdapterListTable';
import { trainingDataApi } from '../../api/trainingData.api';
import type { TrainedAdapterItem, TrainedAdapterListResponse } from '../../types';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: {
    listAdapters: vi.fn(),
    publishAdapter: vi.fn(),
    unpublishAdapter: vi.fn(),
  },
}));

function adapter(version: number, overrides: Partial<TrainedAdapterItem> = {}): TrainedAdapterItem {
  return {
    adapter_id: `ad-${version}`,
    agent_id: 'sme',
    job_id: `job-${version}`,
    version,
    file_sha256: 'a'.repeat(64),
    size_bytes: 1024,
    created_at: '2026-09-20T10:00:00.000Z',
    gguf_filename: `sme-v${version}.gguf`,
    loaded: true,
    published: false,
    ...overrides,
  };
}

function listing(
  adapters: TrainedAdapterItem[],
  overrides: Partial<TrainedAdapterListResponse> = {},
): TrainedAdapterListResponse {
  const published = adapters.find((a) => a.published);
  return {
    agent_id: 'sme',
    adapters,
    published_adapter_id: published?.adapter_id ?? null,
    server_reachable: true,
    unrecognized_server_adapters: [],
    ...overrides,
  };
}

function rowFor(version: number) {
  return screen.getByText(`v${version}`).closest('tr') as HTMLElement;
}

describe('AdapterListTable', () => {
  const writeText = vi.fn();

  beforeEach(() => {
    vi.mocked(trainingDataApi.publishAdapter).mockResolvedValue(listing([]));
    vi.mocked(trainingDataApi.unpublishAdapter).mockResolvedValue(undefined);
    writeText.mockReset();
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  async function renderTable(data: TrainedAdapterListResponse) {
    vi.mocked(trainingDataApi.listAdapters).mockResolvedValue(data);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AdapterListTable agentId="sme" />
      </QueryClientProvider>,
    );
    await screen.findByText(`v${data.adapters[0].version}`);
  }

  it('shows Published, Loaded, Not loaded and Unknown status badges', async () => {
    await renderTable(
      listing([
        adapter(1, { loaded: null }),
        adapter(2, { loaded: false }),
        adapter(3, { loaded: true, published: true }),
      ]),
    );
    expect(within(rowFor(1)).getByText('Unknown')).toBeDefined();
    expect(within(rowFor(2)).getByText('Not loaded')).toBeDefined();
    expect(within(rowFor(3)).getByText('Loaded')).toBeDefined();
    expect(within(rowFor(3)).getByText('Published')).toBeDefined();
    expect(within(rowFor(2)).queryByText('Published')).toBeNull();
  });

  it('enables Publish only for a loaded, unpublished version and confirms before calling', async () => {
    await renderTable(listing([adapter(1, { loaded: true }), adapter(2, { loaded: false })]));
    const notLoaded = within(rowFor(2)).getByRole('button', {
      name: 'Publish',
    });
    expect((notLoaded as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(within(rowFor(1)).getByRole('button', { name: 'Publish' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('Faculty evaluations will use SME v1 from now on');
    expect(trainingDataApi.publishAdapter).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: /confirm|publish/i }));
    await waitFor(() => expect(trainingDataApi.publishAdapter).toHaveBeenCalledWith('sme', 'ad-1'));
  });

  it('shows Unpublish on the published version and calls it after confirming', async () => {
    await renderTable(listing([adapter(1, { published: true }), adapter(2)]));
    expect(within(rowFor(2)).queryByRole('button', { name: 'Unpublish' })).toBeNull();

    fireEvent.click(within(rowFor(1)).getByRole('button', { name: 'Unpublish' }));
    const dialog = await screen.findByRole('dialog');
    expect(trainingDataApi.unpublishAdapter).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: /confirm|unpublish/i }));
    await waitFor(() => expect(trainingDataApi.unpublishAdapter).toHaveBeenCalledWith('sme'));
  });

  it('shows a copyable load flag for a not-loaded version', async () => {
    await renderTable(listing([adapter(1), adapter(4, { loaded: false })]));
    const row = rowFor(4);
    expect(within(row).getByText('--lora-scaled sme-v4.gguf:0.0')).toBeDefined();
    fireEvent.click(within(row).getByRole('button', { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith('--lora-scaled sme-v4.gguf:0.0');
    expect(within(rowFor(1)).queryByText(/--lora-scaled/)).toBeNull();
    expect(within(row).getByText(/full path/)).toBeDefined();
    expect(within(row).getByText(/F:\\Dev\\Models\\gemma\\adapters\\sme-v4\.gguf/)).toBeDefined();
  });

  it('does not throw when the clipboard write is rejected', async () => {
    writeText.mockRejectedValue(new Error('denied'));
    await renderTable(listing([adapter(1), adapter(4, { loaded: false })]));
    fireEvent.click(within(rowFor(4)).getByRole('button', { name: /copy/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalled();
  });

  it('warns when the published adapter is not loaded, and not when it is', async () => {
    await renderTable(listing([adapter(1), adapter(3, { published: true, loaded: false })]));
    expect(screen.getByRole('alert').textContent).toContain(
      'Published adapter v3 is not loaded on the model server',
    );
    cleanup();

    await renderTable(listing([adapter(1), adapter(3, { published: true, loaded: true })]));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('says the server could not be reached and never claims Not loaded', async () => {
    await renderTable(
      listing([adapter(1), adapter(3, { published: true, loaded: null })], {
        server_reachable: false,
      }),
    );
    expect(screen.getByRole('alert').textContent).toMatch(/could not be reached/i);
    expect(screen.queryByText('Not loaded')).toBeNull();
  });

  it('refetches the adapter list after a failed publish so stale state is corrected', async () => {
    vi.mocked(trainingDataApi.publishAdapter).mockRejectedValue(
      new Error('Adapter v1 is not loaded on the model server.'),
    );
    await renderTable(listing([adapter(1, { loaded: true })]));
    expect(trainingDataApi.listAdapters).toHaveBeenCalledTimes(1);
    vi.mocked(trainingDataApi.listAdapters).mockResolvedValue(
      listing([adapter(1, { loaded: false })]),
    );

    fireEvent.click(within(rowFor(1)).getByRole('button', { name: 'Publish' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /confirm|publish/i }));

    await waitFor(() => expect(trainingDataApi.listAdapters).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(within(rowFor(1)).getByText('Not loaded')).toBeDefined());
    const publishButton = within(rowFor(1)).getByRole('button', { name: 'Publish' });
    expect((publishButton as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows the API error message beneath the table when publishing fails', async () => {
    vi.mocked(trainingDataApi.publishAdapter).mockRejectedValue(
      new Error('Adapter v1 is not loaded on the model server.'),
    );
    await renderTable(listing([adapter(1)]));
    fireEvent.click(within(rowFor(1)).getByRole('button', { name: 'Publish' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /confirm|publish/i }));
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain('is not loaded on the model server'),
    );
  });
});
