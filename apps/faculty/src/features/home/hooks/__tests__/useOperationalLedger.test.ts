// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOperationalLedger } from '../useOperationalLedger';
import type { AttentionItem, HomeEvaluationItem } from '../../types';

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
  {
    evaluation_id: 'eval-3',
    document_id: 'doc-3',
    document_title: 'Networks SLM',
    syllabus_id: 'syl-3',
    curriculum_id: 'cur-3',
    status: 'FAILED',
    submitted_at: '2026-08-03T00:00:00Z',
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

describe('useOperationalLedger', () => {
  it('initializes with default tab, page, and paginates items', () => {
    const { result } = renderHook(() => useOperationalLedger(mockEvaluations, mockIssues, 2));

    expect(result.current.activeTab).toBe('evaluations');
    expect(result.current.totalItems).toBe(3);
    expect(result.current.totalPages).toBe(2);
    expect(result.current.safePage).toBe(1);
    expect(result.current.paginatedEvaluations).toHaveLength(2);
    expect(result.current.paginatedEvaluations[0].document_title).toBe('Algorithms SLM');
  });

  it('filters evaluations by search query and resets page', () => {
    const { result } = renderHook(() => useOperationalLedger(mockEvaluations, mockIssues, 2));

    act(() => {
      result.current.setPage(2);
    });
    expect(result.current.page).toBe(2);

    act(() => {
      result.current.handleSearchChange('Data');
    });

    expect(result.current.searchQuery).toBe('Data');
    expect(result.current.page).toBe(1);
    expect(result.current.totalItems).toBe(1);
    expect(result.current.paginatedEvaluations).toHaveLength(1);
    expect(result.current.paginatedEvaluations[0].document_title).toBe('Databases SLM');
  });

  it('switches tabs and resets page', () => {
    const { result } = renderHook(() => useOperationalLedger(mockEvaluations, mockIssues, 2));

    act(() => {
      result.current.handleTabChange('attention');
    });

    expect(result.current.activeTab).toBe('attention');
    expect(result.current.page).toBe(1);
    expect(result.current.totalItems).toBe(1);
    expect(result.current.paginatedIssues).toHaveLength(1);
    expect(result.current.paginatedIssues[0].title).toBe('Extraction Error in Networks');
  });
});
