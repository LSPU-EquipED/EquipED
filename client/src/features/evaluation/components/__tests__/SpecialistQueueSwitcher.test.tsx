// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SpecialistQueueSwitcher } from '../SpecialistQueueSwitcher';
import { evaluationApi } from '../../api/evaluation.api';
import type { DeskQueueItem } from '../../types';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    getDeskQueue: vi.fn(),
  },
}));

const mockItems: DeskQueueItem[] = [
  {
    document_id: 'doc-001',
    title: 'Data Structures and Algorithms',
    course_code: 'CS101',
    program: 'BSCS',
    uploaded_at: '2026-08-20T10:00:00Z',
    my_status: 'READY',
    my_score: null,
    my_adjectival: null,
    peer_completed_count: 0,
    peer_completed_desks: [],
  },
  {
    document_id: 'doc-002',
    title: 'Operating Systems Foundations',
    course_code: 'CS102',
    program: 'BSCS',
    uploaded_at: '2026-08-22T10:00:00Z',
    my_status: 'COMPLETED',
    my_score: 3.85,
    my_adjectival: 'Very Satisfactory',
    peer_completed_count: 3,
    peer_completed_desks: ['sme', 'coordinator', 'gad'],
  },
  {
    document_id: 'doc-003',
    title: 'Database Management Systems',
    course_code: 'IT201',
    program: 'BSIT',
    uploaded_at: '2026-08-25T10:00:00Z',
    my_status: 'EVALUATING',
    my_score: null,
    my_adjectival: null,
    peer_completed_count: 1,
    peer_completed_desks: ['itso'],
  },
];

function renderSwitcher(props: Partial<React.ComponentProps<typeof SpecialistQueueSwitcher>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const defaultProps: React.ComponentProps<typeof SpecialistQueueSwitcher> = {
    targetAgent: 'sme',
    selectedDocumentId: 'doc-001',
    onSelectDocument: vi.fn(),
    items: mockItems,
    ...props,
  };

  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <SpecialistQueueSwitcher {...defaultProps} />
      </QueryClientProvider>,
    ),
    props: defaultProps,
  };
}

describe('SpecialistQueueSwitcher', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(evaluationApi.getDeskQueue).mockReset();
    vi.mocked(evaluationApi.getDeskQueue).mockResolvedValue({
      items: mockItems,
      total: mockItems.length,
    });
  });

  it('renders trigger with selected module title and course code', () => {
    renderSwitcher({ selectedDocumentId: 'doc-001' });

    const trigger = screen.getByRole('combobox', { name: /Active SLM/i });
    expect(trigger).toBeDefined();
    expect(trigger.textContent).toContain('CS101 — Data Structures and Algorithms');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('opens popover when trigger is clicked, revealing search and filter chips', () => {
    renderSwitcher();

    const trigger = screen.getByRole('combobox', { name: /Active SLM/i });
    fireEvent.click(trigger);

    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByPlaceholderText(/Search by title or course code/i)).toBeDefined();
    expect(screen.getByRole('tab', { name: /All/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Pending Review/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Completed/i })).toBeDefined();
  });

  it('displays module metadata and desk status badges', () => {
    renderSwitcher();

    fireEvent.click(screen.getByRole('combobox', { name: /Active SLM/i }));

    // Verify metadata
    expect(screen.getByText('Data Structures and Algorithms')).toBeDefined();
    expect(screen.getByText('Operating Systems Foundations')).toBeDefined();
    expect(screen.getByText('Database Management Systems')).toBeDefined();
    expect(screen.getByText('CS101')).toBeDefined();
    expect(screen.getByText('CS102')).toBeDefined();
    expect(screen.getByText('IT201')).toBeDefined();

    // Verify desk status badges
    expect(screen.getByText('Ready for Review')).toBeDefined();
    expect(screen.getByText(/Evaluated 3.85\/4.00/i)).toBeDefined();
    expect(screen.getByText(/Evaluating…/i)).toBeDefined();
  });

  it('filters modules by status chips (Pending Review, Completed, All)', () => {
    renderSwitcher();

    fireEvent.click(screen.getByRole('combobox', { name: /Active SLM/i }));

    // Filter by Pending Review (doc-001 and doc-003)
    fireEvent.click(screen.getByRole('tab', { name: /Pending Review/i }));
    expect(screen.getByText('Data Structures and Algorithms')).toBeDefined();
    expect(screen.getByText('Database Management Systems')).toBeDefined();
    expect(screen.queryByText('Operating Systems Foundations')).toBeNull();

    // Filter by Completed (doc-002)
    fireEvent.click(screen.getByRole('tab', { name: /Completed/i }));
    expect(screen.queryByText('Data Structures and Algorithms')).toBeNull();
    expect(screen.queryByText('Database Management Systems')).toBeNull();
    expect(screen.getByText('Operating Systems Foundations')).toBeDefined();

    // Filter by All
    fireEvent.click(screen.getByRole('tab', { name: /All/i }));
    expect(screen.getByText('Data Structures and Algorithms')).toBeDefined();
    expect(screen.getByText('Operating Systems Foundations')).toBeDefined();
    expect(screen.getByText('Database Management Systems')).toBeDefined();
  });

  it('filters modules dynamically by search input (title or course code)', () => {
    renderSwitcher();

    fireEvent.click(screen.getByRole('combobox', { name: /Active SLM/i }));
    const searchInput = screen.getByPlaceholderText(/Search by title or course code/i);

    // Search by title substring
    fireEvent.change(searchInput, { target: { value: 'Operating' } });
    expect(screen.getByText('Operating Systems Foundations')).toBeDefined();
    expect(screen.queryByText('Data Structures and Algorithms')).toBeNull();
    expect(screen.queryByText('Database Management Systems')).toBeNull();

    // Search by course code
    fireEvent.change(searchInput, { target: { value: 'IT201' } });
    expect(screen.getByText('Database Management Systems')).toBeDefined();
    expect(screen.queryByText('Operating Systems Foundations')).toBeNull();

    // Search with no results
    fireEvent.change(searchInput, { target: { value: 'Nonexistent Course' } });
    expect(screen.getByText(/No modules match criteria/i)).toBeDefined();
  });

  it('calls onSelectDocument when a module is clicked and closes popover', () => {
    const onSelect = vi.fn();
    renderSwitcher({ onSelectDocument: onSelect });

    fireEvent.click(screen.getByRole('combobox', { name: /Active SLM/i }));
    const targetOption = screen.getByText('Operating Systems Foundations').closest('button');
    fireEvent.click(targetOption!);

    expect(onSelect).toHaveBeenCalledWith('doc-002');
    const trigger = screen.getByRole('combobox', { name: /Active SLM/i });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('supports keyboard navigation: ArrowDown, ArrowUp, Enter, and Escape', () => {
    const onSelect = vi.fn();
    renderSwitcher({ onSelectDocument: onSelect });

    const trigger = screen.getByRole('combobox', { name: /Active SLM/i });
    fireEvent.click(trigger);

    const searchInput = screen.getByPlaceholderText(/Search by title or course code/i);

    // Press ArrowDown to move to second item (doc-002)
    fireEvent.keyDown(searchInput, { key: 'ArrowDown' });
    // Press Enter to select
    fireEvent.keyDown(searchInput, { key: 'Enter' });

    expect(onSelect).toHaveBeenCalledWith('doc-002');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');

    // Reopen and press Escape
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    const searchInputAfterReopen = screen.getByPlaceholderText(/Search by title or course code/i);
    fireEvent.keyDown(searchInputAfterReopen, { key: 'Escape' });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('fetches queue data from evaluationApi.getDeskQueue when items prop is omitted', async () => {
    renderSwitcher({ items: undefined });
    await waitFor(() => {
      expect(evaluationApi.getDeskQueue).toHaveBeenCalledWith('sme', undefined);
    });

    await waitFor(() => {
      const trigger = screen.getByRole('combobox', { name: /Active SLM/i });
      expect(trigger.textContent).toContain('CS101 — Data Structures and Algorithms');
    });
  });
});
