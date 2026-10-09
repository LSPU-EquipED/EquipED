// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdapterLoadHint } from '../AdapterLoadHint';
import { trainingDataApi } from '../../api/trainingData.api';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: { getHostSync: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderHint() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdapterLoadHint filename="sme-v3.gguf" />
    </QueryClientProvider>,
  );
}

describe('AdapterLoadHint', () => {
  it('says the sync script handles the download when a host key is active', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: true });
    renderHint();
    expect(
      await screen.findByText(/host sync script downloads this file by itself/i),
    ).toBeDefined();
    expect(screen.getByText(/restart the model server when it is idle/i)).toBeDefined();
    expect(screen.queryByText(/--lora-scaled/)).toBeNull();
    expect(screen.queryByText(/start-gemma\.bat/)).toBeNull();
  });

  it('shows the manual steps, with one restart, when no host key is active', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: false });
    renderHint();
    expect(await screen.findByText('--lora-scaled sme-v3.gguf:0.0')).toBeDefined();
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/start-gemma\.bat/);
    expect(text.match(/restart/gi)).toHaveLength(1);
    expect(text).not.toMatch(/host sync script/i);
  });

  it('shows the manual steps while the host sync status is unknown', () => {
    vi.mocked(trainingDataApi.getHostSync).mockReturnValue(new Promise(() => {}));
    renderHint();
    expect(screen.getByText('--lora-scaled sme-v3.gguf:0.0')).toBeDefined();
  });
});
