// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { PreferenceLogTable } from '../PreferenceLogTable';
import * as hooksModule from '../../hooks/usePreferenceLogs';
import type { PreferenceLogListResponse } from '../../types';

const mockLogsData: PreferenceLogListResponse = {
  items: [
    {
      log_id: 'log-1',
      evaluation_id: 'eval-1',
      user_id: 'user-faculty-1',
      action: 'EDIT',
      edited_json: {
        score: 4,
        justification: 'Accredited topic depth verified against textbook syllabus.',
      },
      notes: 'Reviewed and corrected after faculty inspection.',
      created_at: '2026-09-01T10:00:00Z',
    },
    {
      log_id: 'log-2',
      evaluation_id: 'eval-2',
      user_id: 'user-faculty-2',
      action: 'ACCEPT',
      edited_json: null,
      notes: null,
      created_at: '2026-09-01T11:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
};

describe('PreferenceLogTable', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderTable() {
    return render(
      <QueryClientProvider client={queryClient}>
        <PreferenceLogTable />
      </QueryClientProvider>,
    );
  }

  it('renders action filter pills and log rows with user ID, action, and score', () => {
    vi.spyOn(hooksModule, 'usePreferenceLogs').mockReturnValue({
      data: mockLogsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePreferenceLogs>);

    renderTable();

    // Action filter buttons
    expect(screen.getByRole('button', { name: 'All Actions' })).toBeDefined();
    expect(screen.getByRole('button', { name: /Score Overrides/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Approved/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Rejections/i })).toBeDefined();

    // Log rows
    expect(screen.getByText('user-faculty-1')).toBeDefined();
    expect(screen.getByText('EDIT')).toBeDefined();
    expect(screen.getByText('eval-1')).toBeDefined();
    expect(screen.getByText('Score: 4')).toBeDefined();

    expect(screen.getByText('user-faculty-2')).toBeDefined();
    expect(screen.getByText('ACCEPT')).toBeDefined();
  });

  it('expands diff drawer and shows justification when clicking View Diff', () => {
    vi.spyOn(hooksModule, 'usePreferenceLogs').mockReturnValue({
      data: mockLogsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePreferenceLogs>);

    renderTable();

    const viewDiffBtn = screen.getByRole('button', { name: /View Diff/i });
    fireEvent.click(viewDiffBtn);

    expect(screen.getByText('Preference Correction Diff')).toBeDefined();
    expect(screen.getByText('Log ID: log-1')).toBeDefined();
    expect(
      screen.getByText('Accredited topic depth verified against textbook syllabus.'),
    ).toBeDefined();
    expect(screen.getByText('Reviewed and corrected after faculty inspection.')).toBeDefined();
  });

  it('renders pagination footer with record counts', () => {
    vi.spyOn(hooksModule, 'usePreferenceLogs').mockReturnValue({
      data: mockLogsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePreferenceLogs>);

    renderTable();

    expect(screen.getByText(/Showing/)).toBeDefined();
    expect(screen.getByText('1–2')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDefined();
  });
});
