import { useId } from "react";
import { TableSkeleton } from "@equiped/ui";
import type { AttentionItem, HomeEvaluationItem } from "../types";
import { useOperationalLedger } from "../hooks/useOperationalLedger";
import { LedgerToolbar } from "./LedgerToolbar";
import { LedgerEvaluationsTable, LedgerAttentionTable } from "./LedgerTables";
import { LedgerPaginationFooter } from "./LedgerPaginationFooter";

export interface FacultyOperationalLedgerProps {
  evaluations?: HomeEvaluationItem[];
  recentIssues?: AttentionItem[];
  isLoading: boolean;
  isError?: boolean;
  onRefresh?: () => void;
}

export function FacultyOperationalLedger({
  evaluations = [],
  recentIssues = [],
  isLoading,
  isError = false,
  onRefresh,
}: FacultyOperationalLedgerProps) {
  const panelId = useId();
  const {
    activeTab,
    searchQuery,
    setPage,
    pageSize,
    handlePageSizeChange,
    paginatedEvaluations,
    paginatedIssues,
    totalItems,
    totalPages,
    safePage,
    handleTabChange,
    handleSearchChange,
  } = useOperationalLedger(evaluations, recentIssues);

  return (
    <section className="w-full min-w-0" aria-labelledby={`${panelId}-heading`}>
      <h2
        id={`${panelId}-heading`}
        className="mb-4 text-base font-semibold text-text"
      >
        Evaluation activity
      </h2>
      <div className="rounded-md border border-border bg-surface">
        <LedgerToolbar
          panelId={panelId}
          activeTab={activeTab}
          evaluationsCount={evaluations.length}
          recentIssuesCount={recentIssues.length}
          searchQuery={searchQuery}
          onTabChange={handleTabChange}
          onSearchChange={handleSearchChange}
          onRefresh={onRefresh}
        />

        <div
          id={panelId}
          role="tabpanel"
          aria-labelledby={`${panelId}-${activeTab}`}
          tabIndex={0}
          className="overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          {isError ? (
            <p
              role="alert"
              className="px-6 py-10 text-center text-sm text-destructive"
            >
              Unable to load evaluation activity.
            </p>
          ) : isLoading ? (
            <TableSkeleton
              ariaLabel="Loading evaluation activity"
              tableClassName="min-w-[40rem]"
              columns={(activeTab === "evaluations"
                ? ["Module", "Status", "Submitted", "Action"]
                : ["Module", "Attention reason", "Action"]
              ).map((label) => ({ label, cellClassName: "py-6" }))}
            />
          ) : activeTab === "evaluations" ? (
            <LedgerEvaluationsTable
              evaluations={paginatedEvaluations}
              isFiltered={Boolean(searchQuery)}
            />
          ) : (
            <LedgerAttentionTable
              issues={paginatedIssues}
              isFiltered={Boolean(searchQuery)}
            />
          )}
        </div>

        {!isLoading && !isError && totalItems > 0 && (
          <LedgerPaginationFooter
            safePage={safePage}
            pageSize={pageSize}
            totalPages={totalPages}
            totalItems={totalItems}
            onPageChange={setPage}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>
    </section>
  );
}
