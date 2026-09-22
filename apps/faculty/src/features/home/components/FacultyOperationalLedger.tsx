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
  const {
    activeTab,
    searchQuery,
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
      aria-label="Recent evaluation activity"
    >
      <LedgerToolbar
        activeTab={activeTab}
        evaluationsCount={evaluations.length}
        recentIssuesCount={recentIssues.length}
        searchQuery={searchQuery}
        onTabChange={handleTabChange}
        onSearchChange={handleSearchChange}
        onRefresh={onRefresh}
      />

      <div className="overflow-x-auto">
        {activeTab === "evaluations" && (
          <LedgerEvaluationsTable
            evaluations={paginatedEvaluations}
            isError={isError}
          />
        )}

        {activeTab === "attention" && (
          <LedgerAttentionTable issues={paginatedIssues} />
        )}
      </div>

      {!isLoading && totalItems > 0 && (
        <LedgerPaginationFooter
          safePage={safePage}
          pageSize={pageSize}
          totalPages={totalPages}
          totalItems={totalItems}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
