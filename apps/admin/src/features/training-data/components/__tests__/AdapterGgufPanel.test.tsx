// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdapterGgufPanel } from '../AdapterGgufPanel';
import { trainingDataApi } from '../../api/trainingData.api';
import { navigateTo } from '../../utils/navigation';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: {
    uploadGguf: vi.fn(),
    deleteGguf: vi.fn(),
    createGgufDownloadLink: vi.fn(),
  },
}));
vi.mock('../../utils/navigation', () => ({ navigateTo: vi.fn() }));

const api = vi.mocked(trainingDataApi);
const absent = {
  adapter_id: 'a-8',
  agent_id: 'sme',
  version: 8,
  gguf_filename: 'sme-v8.gguf',
  gguf: null,
};
const present = {
  ...absent,
  gguf: { size_bytes: 1048576, sha256: 'abc123sha', uploaded_at: '2026-10-05T10:00:00Z' },
};

function renderPanel(adapter: typeof present | typeof absent, published = false) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdapterGgufPanel adapter={adapter as never} published={published} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  });
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it('shows Not uploaded and an upload button when there is no file', () => {
  renderPanel(absent);
  expect(screen.getByText('GGUF file')).toBeDefined();
  expect(screen.getByText('Not uploaded')).toBeDefined();
  expect(screen.getByRole('button', { name: 'Upload GGUF sme-v8.gguf' })).toBeDefined();
});

it('uploads the chosen file once', async () => {
  api.uploadGguf.mockResolvedValue({} as never);
  const { container } = renderPanel(absent);
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input.accept).toBe('.gguf');
  const file = new File(['GGUF'], 'sme-v8.gguf');
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect(api.uploadGguf).toHaveBeenCalledTimes(1));
  expect(api.uploadGguf).toHaveBeenCalledWith('sme', 'a-8', file, false);
});

it('shows an error text when the upload fails', async () => {
  api.uploadGguf.mockRejectedValue(new Error('bad magic'));
  const { container } = renderPanel(absent);
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(['x'], 'sme-v8.gguf')] } });
  expect(await screen.findByRole('alert')).toBeDefined();
  expect(screen.getByText(/bad magic/)).toBeDefined();
});

it('shows size, sha and the three actions when a file exists', () => {
  const { container } = renderPanel(present);
  expect(screen.getByText('1.0 MB')).toBeDefined();
  expect(screen.getByText('abc123sha')).toBeDefined();
  expect(screen.getByRole('button', { name: 'Copy SHA-256 for sme-v8.gguf' })).toBeDefined();
  expect(screen.getByRole('button', { name: 'Download sme-v8.gguf' })).toBeDefined();
  expect(screen.getByRole('button', { name: 'Copy download link for sme-v8.gguf' })).toBeDefined();
  expect(screen.getByRole('button', { name: 'Remove file sme-v8.gguf' })).toBeDefined();
  expect(container.textContent).not.toMatch(/undefined|NaN|null/);
});

it('download requests a link then navigates', async () => {
  api.createGgufDownloadLink.mockResolvedValue({
    url: 'https://x/y.gguf',
    filename: 'sme-v8.gguf',
    sha256: 'abc123sha',
    size_bytes: 1048576,
    expires_at: '2026-10-07T10:00:00Z',
  });
  renderPanel(present);
  fireEvent.click(screen.getByRole('button', { name: 'Download sme-v8.gguf' }));
  await waitFor(() => expect(navigateTo).toHaveBeenCalledWith('https://x/y.gguf'));
  expect(api.createGgufDownloadLink).toHaveBeenCalledWith('sme', 'a-8', 24);
});

it('copy writes the link to the clipboard and shows its expiry', async () => {
  api.createGgufDownloadLink.mockResolvedValue({
    url: 'https://x/y.gguf',
    filename: 'sme-v8.gguf',
    sha256: 'abc123sha',
    size_bytes: 1048576,
    expires_at: '2026-10-07T10:00:00Z',
  });
  renderPanel(present);
  fireEvent.click(screen.getByRole('button', { name: 'Copy download link for sme-v8.gguf' }));
  await waitFor(() =>
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://x/y.gguf'),
  );
  expect(await screen.findByText(/Link valid until/)).toBeDefined();
  expect(screen.queryByText(/Invalid Date/)).toBeNull();
});

it('remove asks for confirmation before deleting', async () => {
  api.deleteGguf.mockResolvedValue(undefined as never);
  renderPanel(present);
  fireEvent.click(screen.getByRole('button', { name: 'Remove file sme-v8.gguf' }));
  expect(api.deleteGguf).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm remove sme-v8.gguf' }));
  await waitFor(() => expect(api.deleteGguf).toHaveBeenCalledWith('sme', 'a-8'));
});

it('cancelling the confirmation does not delete', () => {
  renderPanel(present);
  fireEvent.click(screen.getByRole('button', { name: 'Remove file sme-v8.gguf' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(api.deleteGguf).not.toHaveBeenCalled();
});

it('disables remove for the published adapter with an explanation', () => {
  renderPanel(present, true);
  const btn = screen.getByRole('button', { name: 'Remove file sme-v8.gguf' }) as HTMLButtonElement;
  expect(btn.disabled).toBe(true);
  expect(btn.title).toMatch(/published/i);
});
