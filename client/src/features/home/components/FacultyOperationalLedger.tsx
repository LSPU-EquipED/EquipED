import { useMemo, useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { TARGET_AGENTS, TARGET_AGENT_META, type TargetAgent } from '@/shared/types/evaluations';
import {
  CaretLeft,
  CaretRight,
  CheckCircle,
  FileText,
  MagnifyingGlass,
  PlayCircle,
  Spinner,
  Warning,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES, TABLE_STYLES } from '@/shared/constants/theme';
import { Skeleton } from '@/shared/components/Skeleton';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import type { AttentionItem, HomeEvaluationItem } from '../types';
import {
  formatDateTime,
  getDocumentStatusBadge,
  getEvaluationStatusBadge,
} from '../utils/homeData';

export type LedgerTab = 'evaluations' | 'attention';

interface FacultyOperationalLedgerProps {
  evaluations: HomeEvaluationItem[];
  recentIssues: AttentionItem[];
  isLoading: boolean;
  latestEvalsByDocId?: Record<string, LatestEvaluationItem>;
  latestEvalsState?: { isLoading?: boolean; isError?: boolean; isSuccess?: boolean };
  onEvaluate?: (doc: ClientDocument, agent: TargetAgent) => void;
}

export function FacultyOperationalLedger({
  evaluations,
  recentIssues,
  isLoading,
  latestEvalsByDocId = {},
  latestEvalsState = {},
  onEvaluate,
}: FacultyOperationalLedgerProps) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<LedgerTab>('evaluations');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);


  const filteredEvaluations = useMemo(() => {
    return evaluations.filter((ev) => {
      const title = ev.document_title || '';
      const matchesSearch =
        searchQuery === '' ||
        title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.evaluation_id.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesSearch;
    });
  }, [evaluations, searchQuery]);

  const filteredIssues = useMemo(() => {
    return recentIssues.filter((issue) => {
      const matchesSearch =
        searchQuery === '' ||
        issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        issue.detail.toLowerCase().includes(searchQuery.toLowerCase());

      return matchesSearch;
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


  return (
    <div className={TABLE_STYLES.wrapper}>
      {/* Ledger Navigation & Filter Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-2.5">
        {/* View Tabs */}
        <div className="flex items-center gap-1 -mb-[11px] overflow-x-auto pb-2 md:pb-0" role="tablist" aria-label="Ledger views">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'evaluations'}
            onClick={() => handleTabChange('evaluations')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-3 py-2.5 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'evaluations'
                ? 'border-primary text-primary'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <span>Recent Evaluations</span>
            <span
              className={cn(
                'rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold',
                activeTab === 'evaluations'
                  ? 'bg-primary-soft text-primary'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {evaluations.length}
            </span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'attention'}
            onClick={() => handleTabChange('attention')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-3 py-2.5 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'attention'
                ? 'border-warning text-warning'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <span>Requires Review</span>
            <span
              className={cn(
                'rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold',
                activeTab === 'attention'
                  ? 'bg-warning-soft text-warning'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {recentIssues.length}
            </span>
          </button>
        </div>

        {/* Controls: Program Filter & Search */}
        <div className="flex items-center gap-2 shrink-0">

          <div className="relative min-w-[12rem] sm:min-w-[15rem]">
            <MagnifyingGlass
              className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search in ledger..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      {/* Table Body according to Active Tab */}
      <div className="overflow-x-auto">
        {activeTab === 'evaluations' && (
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>
                  Document / Evaluation ID
                </th>
                <th scope="col" className={TABLE_STYLES.th}>
                  Status
                </th>
                <th scope="col" className={TABLE_STYLES.th}>
                  Submitted
                </th>
                <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {paginatedEvaluations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-text-muted">
                    <p className="font-semibold text-text">No evaluations on record</p>
                    <p className="text-xs text-text-muted mt-1">
                      Completed evaluation scorecards will appear here.
                    </p>
                  </td>
                </tr>
              ) : (
                paginatedEvaluations.map((ev) => {
                  const evalBadge = getEvaluationStatusBadge(ev.status);
                  return (
                    <tr key={ev.evaluation_id} className={TABLE_STYLES.tr}>
                      <td className={TABLE_STYLES.td}>
                        <div className="flex flex-col">
                          <span className="font-semibold text-text">
                            {ev.document_title || 'Untitled SLM'}
                          </span>
                          <span className="text-[11px] font-mono text-text-muted">
                            {ev.evaluation_id}
                          </span>
                        </div>
                      </td>
                      <td className={TABLE_STYLES.td}>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-xs px-2 py-0.5 text-xs font-semibold select-none',
                            evalBadge.className,
                          )}
                        >
                          {evalBadge.label}
                        </span>
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'text-xs text-text-muted tabular-nums')}>
                        {formatDateTime(ev.submitted_at)}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'text-right')}>
                        <Link
                          to="/evaluations/$id"
                          params={{ id: ev.evaluation_id }}
                          className={cn(
                            BUTTON_STYLES.base,
                            BUTTON_STYLES.variants.secondary,
                            BUTTON_STYLES.sizes.sm,
                          )}
                        >
                          <span>View Scorecard</span>
                          <CaretRight className="size-3.5" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}

        {activeTab === 'attention' && (
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>
                  Module
                </th>
                <th scope="col" className={TABLE_STYLES.th}>
                  Attention Reason
                </th>
                <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {paginatedIssues.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-6 py-12 text-center text-sm text-text-muted">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <CheckCircle className="size-6 text-success" aria-hidden="true" />
                      <p className="font-semibold text-text">No action items</p>
                      <p className="text-xs text-text-muted">
                        All modules are processed and evaluated cleanly.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedIssues.map((issue) => (
                  <tr key={issue.id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <span className="font-semibold text-text">{issue.title}</span>
                      <span className="text-xs text-text-muted mt-0.5 block">{issue.detail}</span>
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant="warning" withDot>
                        {issue.type === 'document_failed' ? 'Processing Issue' : 'Evaluation Issue'}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      <Link
                        to={issue.targetUrl}
                        className={cn(
                          BUTTON_STYLES.base,
                          BUTTON_STYLES.variants.secondary,
                          BUTTON_STYLES.sizes.sm,
                        )}
                      >
                        <span>{issue.actionLabel}</span>
                        <CaretRight className="size-3.5" aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Ledger Footer with Compact Pagination */}
      {!isLoading && totalItems > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-border bg-surface-subtle px-4 sm:px-6 py-2.5 text-xs text-text-muted">
          <div className="flex flex-wrap items-center gap-3">
            <span className="tabular-nums font-medium">
              Showing {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, totalItems)} of {totalItems} {activeTab === 'evaluations' ? 'evaluations' : 'issues'}
            </span>
            <span className="text-border">|</span>
            <div className="flex items-center gap-1.5">
              <span>Show</span>
              <select
                aria-label="Rows per page"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="h-7 rounded-sm border border-input bg-surface px-1.5 text-xs font-semibold text-text focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
              </select>
              <span>per page</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={safePage <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="h-7 px-2 text-xs"
                aria-label="Previous page"
              >
                <CaretLeft className="size-3" aria-hidden="true" />
                <span className="hidden sm:inline">Previous</span>
              </Button>
              <span className="px-2 font-medium tabular-nums text-text">
                {safePage} / {totalPages}
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={safePage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="h-7 px-2 text-xs"
                aria-label="Next page"
              >
                <span className="hidden sm:inline">Next</span>
                <CaretRight className="size-3" aria-hidden="true" />
              </Button>
            </div>

            <span className="text-border">|</span>

            <Link
              to="/documents"
              className="font-semibold text-primary hover:text-primary-strong flex items-center gap-1 transition-colors"
            >
              <span>Full Archive</span>
              <CaretRight className="size-3" aria-hidden="true" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
