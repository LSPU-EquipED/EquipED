import { useMemo, useState } from 'react';
import type { AttentionItem, HomeEvaluationItem } from '../types';

export type LedgerTab = 'evaluations' | 'attention';

export function useOperationalLedger(
  evaluations: HomeEvaluationItem[] = [],
  recentIssues: AttentionItem[] = [],
  initialPageSize = 5,
) {
  const [activeTab, setActiveTab] = useState<LedgerTab>('evaluations');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const filteredEvaluations = useMemo(() => {
    if (!searchQuery) return evaluations;
    const q = searchQuery.toLowerCase();
    return evaluations.filter((ev) => {
      const title = ev.document_title || '';
      return (
        title.toLowerCase().includes(q) ||
        ev.evaluation_id.toLowerCase().includes(q)
      );
    });
  }, [evaluations, searchQuery]);

  const filteredIssues = useMemo(() => {
    if (!searchQuery) return recentIssues;
    const q = searchQuery.toLowerCase();
    return recentIssues.filter((issue) => {
      return (
        issue.title.toLowerCase().includes(q) ||
        issue.detail.toLowerCase().includes(q)
      );
    });
  }, [recentIssues, searchQuery]);

  const totalItems =
    activeTab === 'evaluations' ? filteredEvaluations.length : filteredIssues.length;

  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const safePage = Math.min(page, totalPages);

  const paginatedEvaluations = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return filteredEvaluations.slice(start, start + pageSize);
  }, [filteredEvaluations, safePage, pageSize]);

  const paginatedIssues = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return filteredIssues.slice(start, start + pageSize);
  }, [filteredIssues, safePage, pageSize]);

  const handleTabChange = (tab: LedgerTab) => {
    setActiveTab(tab);
    setPage(1);
  };

  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    setPage(1);
  };

  return {
    activeTab,
    searchQuery,
    page,
    setPage,
    pageSize,
    setPageSize,
    filteredEvaluations,
    filteredIssues,
    paginatedEvaluations,
    paginatedIssues,
    totalItems,
    totalPages,
    safePage,
    handleTabChange,
    handleSearchChange,
  };
}
