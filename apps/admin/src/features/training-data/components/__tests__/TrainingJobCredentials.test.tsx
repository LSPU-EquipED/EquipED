// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TrainingJobCredentials } from '../TrainingJobCredentials';
import type { TrainingJobCreateResponse } from '../../types';

const credentials: TrainingJobCreateResponse = {
  job_id: 'job-1',
  agent_id: 'gad',
  status: 'pending',
  download_url: 'https://example.test/download?token=abc',
  upload_url: 'https://example.test/upload?token=def',
  download_expires_at: new Date(Date.now() + 3600000).toISOString(),
  upload_expires_at: new Date(Date.now() + 7200000).toISOString(),
  created_at: new Date().toISOString(),
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function mockClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.assign(navigator, { clipboard: { writeText } });
}

describe('TrainingJobCredentials', () => {
  it('provides labeled read-only URLs for manual copying and an explicit saved action', () => {
    const onSaved = vi.fn();
    render(<TrainingJobCredentials credentials={credentials} onSaved={onSaved} />);
    expect((screen.getByLabelText('Download URL') as HTMLInputElement).value).toBe(
      credentials.download_url,
    );
    expect((screen.getByLabelText('Upload URL') as HTMLInputElement).readOnly).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /saved both URLs/i }));
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it('reports success only after clipboard copying resolves', async () => {
    let resolveCopy!: () => void;
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve;
        }),
    );
    mockClipboard(writeText);
    render(<TrainingJobCredentials credentials={credentials} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Download URL' }));
    expect(writeText).toHaveBeenCalledWith(credentials.download_url);
    expect(screen.queryByText('Copied')).toBeNull();
    await act(async () => resolveCopy());
    expect(screen.getByText('Copied')).toBeDefined();
  });

  it('offers manual copying when clipboard access fails', async () => {
    mockClipboard(vi.fn().mockRejectedValue(new Error('Clipboard blocked')));
    render(<TrainingJobCredentials credentials={credentials} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Download URL' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/copy it manually/));
    expect(screen.queryByText('Copied')).toBeNull();
  });

  it('does not schedule feedback after leaving during a clipboard request', async () => {
    vi.useFakeTimers();
    let resolveCopy!: () => void;
    mockClipboard(
      vi.fn(
        () =>
          new Promise<void>((resolve) => {
            resolveCopy = resolve;
          }),
      ),
    );
    const view = render(<TrainingJobCredentials credentials={credentials} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Download URL' }));
    view.unmount();
    await act(async () => resolveCopy());
    expect(vi.getTimerCount()).toBe(0);
  });

  it('updates expiry and disables copying an expired URL', () => {
    vi.useFakeTimers();
    const expiry = new Date(Date.now() + 65000).toISOString();
    render(
      <TrainingJobCredentials
        credentials={{ ...credentials, download_expires_at: expiry, upload_expires_at: expiry }}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getAllByText('1m remaining')).toHaveLength(2);
    act(() => vi.advanceTimersByTime(65000));
    expect(screen.getAllByText('Expired')).toHaveLength(2);
    expect(
      (screen.getByRole('button', { name: 'Copy Download URL' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    cleanup();
    expect(vi.getTimerCount()).toBe(0);
  });
});
