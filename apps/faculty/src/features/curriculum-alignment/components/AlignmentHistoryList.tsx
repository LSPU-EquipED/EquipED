import { useEffect, useState } from "react";
import {
  ArrowRight,
  CaretLeft,
  CaretRight,
  Trash,
  Warning,
} from "@phosphor-icons/react";
import { Button, Dropdown, Skeleton } from "@equiped/ui";
import { getErrorMessage } from "@equiped/api-client";
import { useDeleteAlignmentCheck } from "../hooks/useDeleteAlignmentCheck";
import { useAlignmentCheckHistory } from "../hooks/useAlignmentCheckHistory";
import { ConfirmDeleteModal } from "./ConfirmDeleteModal";
import type { AlignmentCheckListItem } from "../types";

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

type AlignmentHistoryListProps = {
  onSelect: (item: AlignmentCheckListItem) => void;
};

export function AlignmentHistoryList({ onSelect }: AlignmentHistoryListProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pendingDelete, setPendingDelete] =
    useState<AlignmentCheckListItem | null>(null);
  const history = useAlignmentCheckHistory(page, pageSize);
  const deleteCheck = useDeleteAlignmentCheck();
  const items = history.data?.items ?? [];
  const total = history.data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  useEffect(() => {
    if (history.data && page > totalPages) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPage(totalPages);
    }
  }, [history.data, page, totalPages]);

  function confirmDelete() {
    if (!pendingDelete) return;
    deleteCheck.mutate(pendingDelete.check_id, {
      onSuccess: () => setPendingDelete(null),
    });
  }

  return (
    <section aria-labelledby="curriculum-history-heading" className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2
          id="curriculum-history-heading"
          className="text-base font-semibold text-text"
        >
          Previous checks
        </h2>
        {history.data && total > 0 && (
          <span className="text-xs tabular-nums text-text-muted">
            {total} check{total === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <div className="rounded-md border border-border bg-surface">
        {history.isError ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-6"
          >
            <p className="flex items-center gap-2 text-sm text-destructive">
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              {getErrorMessage(history.error, "Could not load check history.")}
            </p>
            <Button variant="secondary" onClick={() => void history.refetch()}>
              Try again
            </Button>
          </div>
        ) : history.isLoading ? (
          <div
            role="status"
            aria-label="Loading previous curriculum checks"
            className="divide-y divide-border"
          >
            {Array.from({ length: 3 }, (_, index) => (
              <div
                key={index}
                className="flex items-center justify-between gap-6 px-5 py-5 sm:px-6"
              >
                <div className="w-1/2 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="hidden h-10 w-28 sm:block" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-10 sm:px-6">
            <h3 className="text-sm font-medium text-text">No checks yet</h3>
            <p className="mt-1.5 text-sm text-text-muted">
              Your saved checks will appear here.
            </p>
          </div>
        ) : (
          <>
            <div
              aria-hidden="true"
              className="hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_10rem] gap-6 border-b border-border px-6 py-3 text-xs font-medium text-text-muted sm:grid"
            >
              <span>Module / course</span>
              <span>Check</span>
              <span className="text-right">Actions</span>
            </div>
            <ul
              aria-label="Previous curriculum checks"
              className="divide-y divide-border"
            >
              {items.map((item) => (
                <li
                  key={item.check_id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-surface-subtle/30 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_10rem] sm:gap-6 sm:px-6"
                >
                  <div className="col-span-2 min-w-0 sm:col-span-1">
                    <h3 className="break-words text-sm font-semibold leading-relaxed text-text">
                      {item.document_title}
                    </h3>
                    <p className="mt-1 break-words text-xs leading-relaxed text-text-muted">
                      {item.course_title}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p
                      className={`text-sm font-medium ${item.success ? "text-success" : "text-destructive"}`}
                    >
                      {item.success ? "Completed" : "Failed"}
                    </p>
                    <time
                      dateTime={item.run_at}
                      title={new Date(item.run_at).toLocaleString()}
                      className="mt-1 block text-xs tabular-nums text-text-muted"
                    >
                      {dateFormatter.format(new Date(item.run_at))}
                    </time>
                  </div>
                  <div className="flex items-center justify-self-end gap-2">
                    <Button
                      variant="ghost"
                      onClick={() => onSelect(item)}
                      aria-label={`View check for ${item.document_title}`}
                      className="gap-2 px-2 text-sm"
                    >
                      View check
                      <ArrowRight className="size-3.5" aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        deleteCheck.reset();
                        setPendingDelete(item);
                      }}
                      disabled={deleteCheck.isPending}
                      aria-label={`Delete check for ${item.document_title}`}
                      title="Delete check"
                      className="size-10 p-0 hover:bg-destructive-soft hover:text-destructive"
                    >
                      <Trash className="size-4" aria-hidden="true" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3 sm:px-6">
              <div className="flex flex-wrap items-center gap-3">
                <p
                  role="status"
                  className="text-xs tabular-nums text-text-muted"
                >
                  {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)}{" "}
                  of {total} checks
                </p>
                <Dropdown
                  aria-label="Checks per page"
                  size="md"
                  value={pageSize}
                  onChange={(value) => {
                    setPageSize(Number(value));
                    setPage(1);
                  }}
                  options={[10, 25, 50].map((value) => ({
                    value,
                    label: `${value} rows`,
                  }))}
                />
              </div>
              {totalPages > 1 && (
                <nav
                  aria-label="Check history pagination"
                  className="flex items-center gap-2"
                >
                  <Button
                    variant="secondary"
                    aria-label="Previous page"
                    title="Previous page"
                    disabled={page === 1 || history.isFetching}
                    onClick={() => setPage((value) => Math.max(value - 1, 1))}
                  >
                    <CaretLeft className="size-4" aria-hidden="true" />
                  </Button>
                  <span className="text-xs tabular-nums text-text-muted">
                    {page} / {totalPages}
                  </span>
                  <Button
                    variant="secondary"
                    aria-label="Next page"
                    title="Next page"
                    disabled={page === totalPages || history.isFetching}
                    onClick={() =>
                      setPage((value) => Math.min(value + 1, totalPages))
                    }
                  >
                    <CaretRight className="size-4" aria-hidden="true" />
                  </Button>
                </nav>
              )}
            </footer>
          </>
        )}
      </div>
      {pendingDelete && (
        <ConfirmDeleteModal
          title="Delete this check?"
          message={`This will permanently delete the check for "${pendingDelete.document_title}" / "${pendingDelete.course_title}". This cannot be undone.`}
          isPending={deleteCheck.isPending}
          errorMessage={
            deleteCheck.isError
              ? getErrorMessage(
                  deleteCheck.error,
                  "Could not delete this check.",
                )
              : null
          }
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </section>
  );
}
