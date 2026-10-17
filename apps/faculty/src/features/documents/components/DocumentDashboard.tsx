import { useEffect, useMemo, useState } from "react";
import { useLocation } from "@tanstack/react-router";
import {
  CheckCircle,
  MagnifyingGlass,
  UploadSimple,
  Warning,
} from "@phosphor-icons/react";
import { getErrorMessage } from "@equiped/api-client";
import { Button, Input } from "@equiped/ui";
import { useSlmStorage } from "../hooks/useSlmStorage";
import { StorageToolbar } from "./StorageToolbar";
import { DocumentTable } from "./DocumentTable";
import { DocumentTableSkeleton } from "./DocumentTableSkeleton";
import { DocumentPagination } from "./DocumentPagination";
import { ModuleInspectorDrawer } from "./ModuleInspectorDrawer";
import { StorageUploadModal } from "./StorageUploadModal";

export function DocumentDashboard() {
  const location = useLocation();
  const highlightId = useMemo(
    () => new URLSearchParams(location.search).get("highlight"),
    [location.search],
  );
  const openUploadFromDashboard = useMemo(
    () => new URLSearchParams(location.search).get("upload") === "true",
    [location.search],
  );
  const [flashId, setFlashId] = useState<string | null>(highlightId ?? null);
  const {
    documents,
    total,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    isLoading,
    isFetching,
    error,
    refetch,
    search,
    setSearch,
    programFilter,
    setProgramFilter,
    statusFilter,
    setStatusFilter,
    sortOption,
    setSortOption,
    resetFilters,
    inspectingDoc,
    setInspectingDoc,
    isUploadOpen,
    setIsUploadOpen,
    handleUploadComplete,
  } = useSlmStorage();
  const hasFilters =
    Boolean(search.trim()) || programFilter !== "ALL" || statusFilter !== "all";

  useEffect(() => {
    if (flashId) {
      const timer = setTimeout(() => setFlashId(null), 6000);
      return () => clearTimeout(timer);
    }
  }, [flashId]);
  useEffect(() => {
    if (openUploadFromDashboard) setIsUploadOpen(true);
  }, [openUploadFromDashboard, setIsUploadOpen]);

  return (
    <section className="mx-auto w-full max-w-[108rem] space-y-4 px-4 py-6 sm:px-7 sm:py-8">
      <h1 className="sr-only">Module library</h1>
      {flashId && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-sm border border-success/30 bg-success-soft px-4 py-3 text-sm text-success"
        >
          <CheckCircle className="size-4 shrink-0" aria-hidden="true" />
          SLM uploaded to Module library.
        </div>
      )}
      <div className="rounded-md border border-border bg-surface">
        <div className="flex flex-col gap-3 border-b border-border px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="relative w-full sm:max-w-lg">
            <MagnifyingGlass
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            />
            <Input
              type="search"
              placeholder="Search modules or course details…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Search course modules"
              className="pl-9"
            />
          </div>
          <Button
            onClick={() => setIsUploadOpen(true)}
            className="shrink-0 gap-2"
          >
            <UploadSimple className="size-4" aria-hidden="true" />
            Upload SLM
          </Button>
        </div>
        <div className="border-b border-border bg-surface-subtle/40 px-5 py-4 sm:px-6">
          <StorageToolbar
            programFilter={programFilter}
            setProgramFilter={setProgramFilter}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            sortOption={sortOption}
            setSortOption={setSortOption}
          />
        </div>
        <div
          role="region"
          aria-label="Module Library inventory"
          aria-busy={Boolean(isFetching)}
        >
          {error ? (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-6"
            >
              <p className="flex items-center gap-2 text-sm text-destructive">
                <Warning className="size-4 shrink-0" aria-hidden="true" />
                {getErrorMessage(error, "Unable to load modules.")}
              </p>
              <Button variant="secondary" onClick={() => void refetch()}>
                Try again
              </Button>
            </div>
          ) : isLoading && documents.length === 0 ? (
            <DocumentTableSkeleton />
          ) : documents.length === 0 ? (
            <div className="px-5 py-12 text-center sm:px-6">
              <h2 className="text-base font-semibold text-text">
                {hasFilters ? "No matching modules" : "Your library is empty"}
              </h2>
              <p className="mt-2 text-sm text-text-muted">
                {hasFilters
                  ? "Try another search, program, or file status."
                  : "Upload an SLM in PDF format to begin."}
              </p>
              {hasFilters && (
                <Button
                  variant="secondary"
                  onClick={resetFilters}
                  className="mt-5"
                >
                  Clear filters
                </Button>
              )}
            </div>
          ) : (
            <DocumentTable
              documents={documents}
              flashId={flashId}
              onInspect={setInspectingDoc}
            />
          )}
        </div>
        {!error && !isLoading && (
          <DocumentPagination
            page={page}
            setPage={setPage}
            pageSize={pageSize}
            setPageSize={setPageSize}
            totalPages={totalPages}
            total={total}
            isFetching={isFetching}
            hasFilters={hasFilters && documents.length > 0}
            onResetFilters={resetFilters}
          />
        )}
      </div>
      <ModuleInspectorDrawer
        document={inspectingDoc}
        onClose={() => setInspectingDoc(null)}
      />
      <StorageUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadComplete}
      />
    </section>
  );
}
