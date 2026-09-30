// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
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
        justification:
          'Accredited topic depth verified against textbook syllabus.',
        criterion_id: 'OP-01',
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

function mockQuery(
  data = mockLogsData,
  state = { isLoading: false, isError: false },
) {
  return vi.spyOn(hooksModule, 'usePreferenceLogs').mockReturnValue({
    data,
    ...state,
  } as ReturnType<typeof hooksModule.usePreferenceLogs>);
}

describe('PreferenceLogTable', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders concise labels, scores, and one record count', () => {
    mockQuery();
    render(<PreferenceLogTable />);

    expect(
      screen
        .getByRole('button', { name: 'All actions' })
        .getAttribute('aria-pressed'),
    ).toBe('true');
    for (const label of ['Edited', 'Accepted', 'Rejected']) {
      expect(screen.getByRole('button', { name: label })).toBeDefined();
    }
    const table = within(
      screen.getByRole('table', { name: 'Preference logs' }),
    );
    expect(table.getByRole('cell', { name: 'Edited' })).toBeDefined();
    expect(table.getByRole('cell', { name: 'Accepted' })).toBeDefined();
    expect(table.getByRole('cell', { name: '4' })).toBeDefined();
    expect(table.getByText('user-faculty-1')).toBeDefined();
    expect(table.getByText('eval-1')).toBeDefined();
    expect(screen.getAllByText(/Showing/)).toHaveLength(1);
    expect(screen.getByText('1–2')).toBeDefined();
    expect(
      (screen.getByRole('button', { name: 'Previous' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it('expands accessible review details and keeps additional recorded fields available', () => {
    mockQuery();
    render(<PreferenceLogTable />);

    const toggle = screen.getByRole('button', {
      name: 'View details for log log-1',
    });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    const details = document.getElementById(
      toggle.getAttribute('aria-controls')!,
    );
    expect(details).not.toBeNull();
    const drawer = within(details!);
    expect(
      drawer.getByRole('heading', { name: 'Review details' }),
    ).toBeDefined();
    expect(drawer.getByText('log-1')).toBeDefined();
    expect(
      drawer.getByText(
        'Accredited topic depth verified against textbook syllabus.',
      ),
    ).toBeDefined();
    expect(
      drawer.getByText('Reviewed and corrected after faculty inspection.'),
    ).toBeDefined();
    const disclosure = drawer.getByText('Recorded data').closest('details')!;
    fireEvent.click(drawer.getByText('Recorded data'));
    expect(disclosure.open).toBe(true);
    expect(JSON.parse(disclosure.querySelector('pre')!.textContent!)).toEqual(
      mockLogsData.items[0].edited_json,
    );
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(
      screen.queryByRole('heading', { name: 'Review details' }),
    ).toBeNull();
  });

  it('makes identifiers accessible even when no correction or notes were recorded', () => {
    mockQuery();
    render(<PreferenceLogTable />);
    const toggle = screen.getByRole('button', {
      name: 'View details for log log-2',
    });
    fireEvent.click(toggle);
    const drawer = within(
      document.getElementById(toggle.getAttribute('aria-controls')!)!,
    );
    expect(drawer.getByText('log-2')).toBeDefined();
    expect(drawer.getByText('user-faculty-2')).toBeDefined();
    expect(drawer.getByText('eval-2')).toBeDefined();
    expect(drawer.queryByText('Recorded data')).toBeNull();
  });

  it.each([
    ['ITEM_ACCEPT', 'Item accepted'],
    ['ITEM_REJECT', 'Item rejected'],
    ['FUTURE_ACTION', 'FUTURE_ACTION'],
  ])('renders action %s without losing its meaning', (action, label) => {
    mockQuery({
      ...mockLogsData,
      items: [{ ...mockLogsData.items[0], action }],
    });
    render(<PreferenceLogTable />);
    expect(screen.getByRole('cell', { name: label })).toBeDefined();
  });

  it('preserves a zero score and non-text justification in recorded data', () => {
    const edited = {
      score: 0,
      justification: { reason: 'Recorded structured feedback' },
    };
    mockQuery({
      ...mockLogsData,
      items: [{ ...mockLogsData.items[0], edited_json: edited }],
    });
    render(<PreferenceLogTable />);
    expect(screen.getByRole('cell', { name: '0' })).toBeDefined();
    fireEvent.click(
      screen.getByRole('button', { name: 'View details for log log-1' }),
    );
    expect(screen.queryByText('[object Object]')).toBeNull();
    const disclosure = screen.getByText('Recorded data').closest('details')!;
    expect(JSON.parse(disclosure.querySelector('pre')!.textContent!)).toEqual(
      edited,
    );
  });

  it('resets pagination when filtering and changing page size through the shared dropdown', () => {
    const query = mockQuery({ ...mockLogsData, total: 30 });
    render(<PreferenceLogTable />);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(query).toHaveBeenLastCalledWith({
      action: undefined,
      page: 2,
      page_size: 10,
    });
    fireEvent.click(screen.getByRole('button', { name: 'Edited' }));
    expect(query).toHaveBeenLastCalledWith({
      action: 'EDIT',
      page: 1,
      page_size: 10,
    });
    expect(
      screen
        .getByRole('button', { name: 'Edited' })
        .getAttribute('aria-pressed'),
    ).toBe('true');
    expect(
      screen
        .getByRole('button', { name: 'All actions' })
        .getAttribute('aria-pressed'),
    ).toBe('false');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    const pageSize = screen.getByRole('button', { name: 'Records per page' });
    fireEvent.keyDown(pageSize, { key: 'Enter' });
    const listbox = screen.getByRole('listbox', { name: 'Rows per page' });
    fireEvent.keyDown(listbox, { key: 'ArrowDown' });
    fireEvent.keyDown(listbox, { key: 'Enter' });
    expect(query).toHaveBeenLastCalledWith({
      action: 'EDIT',
      page: 1,
      page_size: 20,
    });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(pageSize);
  });

  it('distinguishes an empty history from an empty filter and supports clearing the filter', () => {
    const query = mockQuery({ ...mockLogsData, items: [], total: 0 });
    render(<PreferenceLogTable />);
    expect(screen.getByText('No preference logs yet')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Rejected' }));
    expect(screen.getByText('No matching records')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filter' }));
    expect(query).toHaveBeenLastCalledWith({
      action: undefined,
      page: 1,
      page_size: 10,
    });
    expect(screen.getByText('No preference logs yet')).toBeDefined();
  });

  it('preserves independent row expansion across page and filter changes', () => {
    vi.spyOn(hooksModule, 'usePreferenceLogs').mockImplementation(
      (params = {}) => {
        const item =
          params.page === 2 || params.action === 'ACCEPT'
            ? mockLogsData.items[1]
            : mockLogsData.items[0];
        return {
          data: { ...mockLogsData, items: [item], total: 20 },
          isLoading: false,
          isError: false,
        } as ReturnType<typeof hooksModule.usePreferenceLogs>;
      },
    );
    render(<PreferenceLogTable />);

    fireEvent.click(
      screen.getByRole('button', { name: 'View details for log log-1' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      screen.queryByRole('button', { name: 'Hide details for log log-1' }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole('button', { name: 'View details for log log-2' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(
      screen
        .getByRole('button', { name: 'Hide details for log log-1' })
        .getAttribute('aria-expanded'),
    ).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Accepted' }));
    expect(
      screen
        .getByRole('button', { name: 'Hide details for log log-2' })
        .getAttribute('aria-expanded'),
    ).toBe('true');
    fireEvent.click(
      screen.getByRole('button', { name: 'Hide details for log log-2' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'All actions' }));
    expect(
      screen
        .getByRole('button', { name: 'Hide details for log log-1' })
        .getAttribute('aria-expanded'),
    ).toBe('true');
  });

  it('announces query errors without showing misleading empty history', () => {
    mockQuery(mockLogsData, { isLoading: false, isError: true });
    render(<PreferenceLogTable />);
    expect(screen.getByRole('alert').textContent).toContain(
      'Unable to load preference logs',
    );
    expect(screen.queryByText('No preference logs yet')).toBeNull();
    expect(
      screen.queryByRole('navigation', { name: 'Preference log pagination' }),
    ).toBeNull();
  });
});
