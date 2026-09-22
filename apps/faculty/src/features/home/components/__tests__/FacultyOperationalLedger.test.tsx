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

    expect(screen.getByText('Recent evaluation activity')).toBeDefined();
    expect(screen.getByText('Algorithms SLM')).toBeDefined();
    expect(screen.getByText('Databases SLM')).toBeDefined();
    expect(screen.getByText('eval-1')).toBeDefined();
    expect(screen.getByText('eval-2')).toBeDefined();
  });

  it('switches between Recent Evaluations and Requires Review tabs', () => {
    render(
      <FacultyOperationalLedger
        evaluations={mockEvaluations}
        recentIssues={mockIssues}
        isLoading={false}
      />,
    );

    const reviewTab = screen.getByRole('tab', { name: /Requires Review/i });
    fireEvent.click(reviewTab);

    expect(screen.getByText('Extraction Error in Networks')).toBeDefined();
    expect(screen.getByText('OCR unreadable on page 4')).toBeDefined();
    expect(screen.getByText('Processing Issue')).toBeDefined();
    expect(screen.queryByText('Algorithms SLM')).toBeNull();

    const evalTab = screen.getByRole('tab', { name: /Recent Evaluations/i });
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
});
