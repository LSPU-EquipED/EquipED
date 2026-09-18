// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { TrainingJobCredentials } from '../TrainingJobCredentials';
import type { TrainingJobCreateResponse } from '../../types';

describe('TrainingJobCredentials', () => {
  const credentials: TrainingJobCreateResponse = {
    job_id: 'job-1',
    agent_id: 'gad',
    status: 'pending',
    download_url: 'https://example.test/download?token=abc',
    upload_url: 'https://example.test/upload?token=def',
    download_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    upload_expires_at: new Date(Date.now() + 120 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('renders download and upload credential fields with copy buttons', () => {
    render(<TrainingJobCredentials credentials={credentials} />);

    expect(screen.getByText('Download URL (notebook cell 1)')).toBeDefined();
    expect(screen.getByText('Upload URL (notebook final cell)')).toBeDefined();
    expect(screen.getByText('https://example.test/download?token=abc')).toBeDefined();
    expect(screen.getByText('https://example.test/upload?token=def')).toBeDefined();
    expect(screen.getAllByRole('button', { name: /copy/i })).toHaveLength(2);
  });

  it('copies URL to clipboard and toggles button label', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText,
      },
    });

    render(<TrainingJobCredentials credentials={credentials} />);

    const [firstCopyButton] = screen.getAllByRole('button', { name: /copy/i });
    fireEvent.click(firstCopyButton);

    expect(writeText).toHaveBeenCalledWith('https://example.test/download?token=abc');
    expect(screen.getByText('Copied')).toBeDefined();
  });

  it('updates countdown via 1-second interval', () => {
    vi.useFakeTimers();
    const futureExpiry = new Date(Date.now() + 65 * 1000).toISOString();
    const testCreds = {
      ...credentials,
      download_expires_at: futureExpiry,
      upload_expires_at: futureExpiry,
    };

    render(<TrainingJobCredentials credentials={testCreds} />);
    expect(screen.getAllByText('1m remaining')).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(6000);
    });

    expect(screen.getAllByText('0m remaining')).toHaveLength(2);
  });
});
