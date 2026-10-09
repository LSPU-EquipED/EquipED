// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HostSyncPanel } from '../HostSyncPanel';
import { trainingDataApi } from '../../api/trainingData.api';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: {
    getHostSync: vi.fn(),
    createHostKey: vi.fn(),
    revokeHostKey: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HostSyncPanel />
    </QueryClientProvider>,
  );
}

describe('HostSyncPanel', () => {
  it('offers to create a key when none exists', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: false });
    renderPanel();
    expect(await screen.findByRole('button', { name: /create host key/i })).toBeDefined();
    expect(screen.getByText(/no key yet/i)).toBeDefined();
  });

  it('shows the new key once after creating it', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: false });
    vi.mocked(trainingDataApi.createHostKey).mockResolvedValue({
      key: 'hsk_secret123',
      created_at: '2026-10-10T00:00:00Z',
    });
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: /create host key/i }));
    expect(((await screen.findByLabelText('Host key')) as HTMLInputElement).value).toBe(
      'hsk_secret123',
    );
    expect(screen.getByText(/shown once/i)).toBeDefined();
  });

  it('shows when the host last checked and can revoke the key', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({
      has_active_key: true,
      created_at: '2026-10-09T00:00:00Z',
      last_seen_at: new Date(Date.now() - 4 * 60_000).toISOString(),
    });
    vi.mocked(trainingDataApi.revokeHostKey).mockResolvedValue(undefined);
    renderPanel();
    expect(await screen.findByText(/last checked 4 min ago/i)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /revoke key/i }));
    await waitFor(() => expect(trainingDataApi.revokeHostKey).toHaveBeenCalled());
  });

  it('says the host has not checked in yet', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({
      has_active_key: true,
      created_at: '2026-10-09T00:00:00Z',
      last_seen_at: null,
    });
    renderPanel();
    expect(await screen.findByText(/has not checked in yet/i)).toBeDefined();
  });
});
