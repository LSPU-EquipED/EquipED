import { Link } from '@tanstack/react-router';
import {
  ArrowsClockwise,
  CaretLeft,
  CaretRight,
  CheckCircle,
  MagnifyingGlass,
} from '@phosphor-icons/react';
import { Badge, Button, cn } from '@equiped/ui';
import type { AttentionItem, HomeEvaluationItem } from '../types';
import { useOperationalLedger } from '../hooks/useOperationalLedger';
import { formatDateTime, getEvaluationStatusBadge } from '../utils/homeData';

export type LedgerTab = 'evaluations' | 'attention';

export interface FacultyOperationalLedgerProps {
  evaluations?: HomeEvaluationItem[];
  recentIssues?: AttentionItem[];
  isLoading: boolean;
  onRefresh?: () => void;
}

export function FacultyOperationalLedger({
  evaluations = [],
  recentIssues = [],
  isLoading,
  onRefresh,
}: FacultyOperationalLedgerProps) {
  const {
    activeTab,
    searchQuery,
    page,
    setPage,
    pageSize,
    setPageSize,
    paginatedEvaluations,
    paginatedIssues,
    totalItems,
    totalPages,
    safePage,
    handleTabChange,
    handleSearchChange,
  } = useOperationalLedger(evaluations, recentIssues);

  return (
    <div
      className="w-full rounded-md border border-border bg-surface overflow-hidden shadow-none"
      role="region"
      aria-label="Faculty Command Ledger"
    >
      {/* ── Toolbar: Level Header Strip ────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-3">
        {/* Left: Section Stamp & Unified Segment Switcher */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-bold text-text tracking-tight shrink-0 select-none">
            Faculty Command Ledger
          </span>

          <div className="hidden sm:block h-4 w-px bg-border shrink-0" aria-hidden="true" />

          <div
            role="tablist"
            aria-label="Ledger views"
            className="flex items-center gap-1 rounded-sm bg-surface-subtle p-1 border border-border/60"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'evaluations'}
              onClick={() => handleTabChange('evaluations')}
              className={cn(
                'flex items-center gap-2 rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer select-none',
                activeTab === 'evaluations'
                  ? 'bg-surface text-primary font-bold shadow-xs border border-border/80'
                  : 'text-text-muted hover:text-text',
              )}
            >
              <span>Recent Evaluations</span>
              <span
                className={cn(
                  'rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold',
                  activeTab === 'evaluations'
                    ? 'bg-primary-soft text-primary'
                    : 'bg-surface text-text-muted',
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
                'flex items-center gap-2 rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer select-none',
                activeTab === 'attention'
                  ? 'bg-surface text-warning font-bold shadow-xs border border-border/80'
                  : 'text-text-muted hover:text-text',
              )}
            >
              <span>Requires Review</span>
              <span
                className={cn(
                  'rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold',
                  activeTab === 'attention'
                    ? 'bg-warning-soft text-warning'
                    : 'bg-surface text-text-muted',
                )}
              >
                {recentIssues.length}
              </span>
            </button>
          </div>
        </div>

        {/* Right: Search & Refresh */}
        <div className="flex items-center gap-2 shrink-0">
          {onRefresh && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onRefresh}
              className="h-8.5 px-3 text-xs font-semibold gap-1.5 shrink-0 border-border hover:bg-surface-subtle"
              title="Refresh workspace data"
            >
              <ArrowsClockwise className="size-3.5" aria-hidden="true" />
              <span>Refresh</span>
            </Button>
          )}

          <div className="relative min-w-[12rem] sm:min-w-[15rem]">
            <MagnifyingGlass
              className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search evaluations..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      {/* ── Table Body: Leveled Edge Padding ──────────────────────────── */}
      <div className="overflow-x-auto">
        {activeTab === 'evaluations' && (
          <table className="w-full text-left border-collapse">
            <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
              <tr>
                <th scope="col" className="pl-4 sm:pl-6 pr-4 py-3 min-w-[18rem] text-left">
                  Document / Evaluation ID
                </th>
                <th scope="col" className="px-4 py-3 text-left">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 text-left">
                  Submitted
                </th>
                <th scope="col" className="pl-4 pr-4 sm:pr-6 py-3 text-right">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface text-sm text-text">
              {paginatedEvaluations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-text-muted">
                    <p className="font-semibold text-text">No evaluations on record</p>
                    <p className="text-xs text-text-muted mt-1">
                      Completed and in-progress evaluation scorecards will appear here once submitted.
                    </p>
                  </td>
                </tr>
              ) : (
                paginatedEvaluations.map((ev) => {
                  const evalBadge = getEvaluationStatusBadge(ev.status);
                  return (
                    <tr key={ev.evaluation_id} className="transition-colors hover:bg-surface-subtle/70">
                      <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                        <div className="space-y-0.5">
                          <span className="text-sm font-semibold text-text block leading-snug">
                            {ev.document_title || 'Untitled SLM'}
                          </span>
                          <span className="text-[11px] font-mono text-text-muted block tabular-nums">
                            {ev.evaluation_id}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-xs px-2.5 py-0.5 text-xs font-semibold select-none',
                            evalBadge.className,
                          )}
                        >
                          {evalBadge.label}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-text-muted tabular-nums">
                        {formatDateTime(ev.submitted_at)}
                      </td>
                      <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                        <Link
                          to="/evaluations/$id"
                          params={{ id: ev.evaluation_id }}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-strong hover:underline transition-colors"
                        >
                          <span>View Scorecard</span>
                          <CaretRight className="size-3" aria-hidden="true" />
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
          <table className="w-full text-left border-collapse">
            <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
              <tr>
                <th scope="col" className="pl-4 sm:pl-6 pr-4 py-3 min-w-[18rem] text-left">
                  Module
                </th>
                <th scope="col" className="px-4 py-3 text-left">
                  Attention Reason
                </th>
                <th scope="col" className="pl-4 pr-4 sm:pr-6 py-3 text-right">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface text-sm text-text">
              {paginatedIssues.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-6 py-12 text-center text-sm text-text-muted">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <CheckCircle className="size-6 text-success" aria-hidden="true" />
                      <p className="font-semibold text-text">No action items</p>
                      <p className="text-xs text-text-muted">
                        All modules are processed and evaluated without active errors.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedIssues.map((issue) => (
                  <tr key={issue.id} className="transition-colors hover:bg-surface-subtle/70">
                    <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                      <span className="font-semibold text-text">{issue.title}</span>
                      <span className="text-xs text-text-muted mt-0.5 block">{issue.detail}</span>
                    </td>
                    <td className="px-4 py-3.5">
                      <Badge variant="warning" withDot>
                        {issue.type === 'document_failed' ? 'Processing Issue' : 'Evaluation Issue'}
                      </Badge>
                    </td>
                    <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                      <Link
                        to={issue.targetUrl}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-strong hover:underline transition-colors"
                      >
                        <span>{issue.actionLabel}</span>
                        <CaretRight className="size-3" aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Ledger Footer: Leveled Edge Padding ───────────────────────── */}
      {!isLoading && totalItems > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-border bg-surface-subtle px-4 sm:px-6 py-2.5 text-xs text-text-muted">
          <div className="flex flex-wrap items-center gap-3">
            <span className="tabular-nums font-medium">
              Showing {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, totalItems)} of {totalItems} items
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
