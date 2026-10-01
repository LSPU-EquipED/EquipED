// @vitest-environment jsdom
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { FacultyOperationalLedger } from '../FacultyOperationalLedger';
import type { AttentionItem, HomeEvaluationItem } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    className,
  }: {
    children: React.ReactNode;
    to: string;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

const mockEvaluations: HomeEvaluationItem[] = [
  {
    evaluation_id: 'eval-1',
    document_id: 'doc-1',
    document_title: 'Algorithms SLM',
    syllabus_id: 'syl-1',
    curriculum_id: 'cur-1',
    status: 'COMPLETED',
    submitted_at: '2026-08-01T00:00:00Z',
  },
  {
    evaluation_id: 'eval-2',
    document_id: 'doc-2',
    document_title: 'Databases SLM',
    syllabus_id: 'syl-2',
    curriculum_id: 'cur-2',
    status: 'EVALUATING',
    submitted_at: '2026-08-02T00:00:00Z',
  },
];

const mockIssues: AttentionItem[] = [
  {
    id: 'issue-1',
    title: 'Extraction Error in Networks',
    detail: 'OCR unreadable on page 4',
    type: 'document_failed',
    timestamp: '2026-08-03T00:00:00Z',
    targetUrl: '/documents',
    actionLabel: 'Review document',
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('FacultyOperationalLedger', () => {
  it('renders recent evaluations by default and displays table rows', () => {
    render(
      <FacultyOperationalLedger
        evaluations={mockEvaluations}
        recentIssues={mockIssues}
        isLoading={false}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Evaluation activity', level: 2 })).toBeDefined();
    expect(screen.getByText('Algorithms SLM')).toBeDefined();
    expect(screen.getByText('Databases SLM')).toBeDefined();
    expect(screen.queryByText('eval-1')).toBeNull();
    expect(screen.queryByText('eval-2')).toBeNull();
    expect(screen.getAllByText(/^[A-Z][a-z]{2} \d{1,2}, 2026$/)).toHaveLength(2);
  });

  it('switches between Recent evaluations and Requires review tabs', () => {
    render(
      <FacultyOperationalLedger
        evaluations={mockEvaluations}
        recentIssues={mockIssues}
        isLoading={false}
      />,
    );

    const reviewTab = screen.getByRole('tab', { name: /Requires review/i });
    fireEvent.click(reviewTab);

    expect(screen.getByText('Extraction Error in Networks')).toBeDefined();
    expect(screen.getByText('OCR unreadable on page 4')).toBeDefined();
    expect(screen.getByText('Processing issue')).toBeDefined();
    expect(screen.queryByText('Algorithms SLM')).toBeNull();

    const evalTab = screen.getByRole('tab', { name: /Recent evaluations/i });
    fireEvent.click(evalTab);

    expect(screen.getByText('Algorithms SLM')).toBeDefined();
  });

  it('renders error state when isError is true', () => {
    render(
      <FacultyOperationalLedger
        evaluations={[]}
        recentIssues={[]}
        isLoading={false}
        isError={true}
      />,
    );

    expect(screen.getByText('Unable to load evaluation activity.')).toBeDefined();
  });

  it('renders empty signal when there are no records', () => {
    render(
      <FacultyOperationalLedger
        evaluations={[]}
        recentIssues={[]}
        isLoading={false}
      />,
    );

    expect(screen.getByText('No evaluations on record')).toBeDefined();
  });

  it('calls onRefresh callback when refresh button is clicked', () => {
    const handleRefresh = vi.fn();
    render(
      <FacultyOperationalLedger
        evaluations={mockEvaluations}
        recentIssues={mockIssues}
        isLoading={false}
        onRefresh={handleRefresh}
      />,
    );

    const refreshBtn = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });

  it('shows loading feedback instead of an empty record message', () => {
    render(<FacultyOperationalLedger isLoading />);

    expect(screen.getByRole('status', { name: 'Loading evaluation activity' })).toBeDefined();
    expect(screen.queryByText('No evaluations on record')).toBeNull();
  });

  it('distinguishes an unmatched search from an empty ledger', () => {
    render(<FacultyOperationalLedger evaluations={mockEvaluations} isLoading={false} />);

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search evaluations' }), {
      target: { value: 'no such module' },
    });
    expect(screen.getByText(/No matching evaluations/)).toBeDefined();
    expect(screen.queryByText('No evaluations on record')).toBeNull();

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '' } });
    expect(screen.getByText('Algorithms SLM')).toBeDefined();
  });

  it('supports arrow-key tab navigation and keeps errors visible in both views', () => {
    render(<FacultyOperationalLedger isLoading={false} isError />);
    const evaluationsTab = screen.getByRole('tab', { name: /Recent evaluations/ });
    evaluationsTab.focus();
    fireEvent.keyDown(evaluationsTab, { key: 'ArrowRight' });

    const reviewTab = screen.getByRole('tab', { name: /Requires review/ });
    expect(document.activeElement).toBe(reviewTab);
    expect(reviewTab.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(reviewTab.id);
    expect(screen.getByText('Unable to load evaluation activity.')).toBeDefined();
    expect(screen.queryByText('No action items')).toBeNull();

    fireEvent.keyDown(reviewTab, { key: 'Home' });
    expect(document.activeElement).toBe(evaluationsTab);
  });

  it('changes page size through the shared dropdown and returns to the first page', () => {
    const evaluations = Array.from({ length: 12 }, (_, index) => ({
      ...mockEvaluations[0],
      evaluation_id: `eval-${index + 1}`,
      document_title: `Module ${index + 1}`,
    }));
    render(<FacultyOperationalLedger evaluations={evaluations} isLoading={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(screen.getByText('Module 6')).toBeDefined();
    expect(screen.queryByText('Module 1')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Rows per page' }));
    fireEvent.click(screen.getByRole('option', { name: '10 rows' }));
    expect(screen.getByText('Module 1')).toBeDefined();
    expect(screen.getByText('Module 10')).toBeDefined();
    expect(screen.queryByText('Module 11')).toBeNull();
    expect(screen.getByRole('button', { name: 'Previous page' }).hasAttribute('disabled')).toBe(true);
  });
});
