import { Link } from "@tanstack/react-router";
import {
  CaretLeft,
  CaretRight,
  MagnifyingGlass,
  Warning,
} from "@phosphor-icons/react";
import { getErrorMessage } from "@equiped/api-client";
import {
  Button,
  Dropdown,
  Input,
  Skeleton,
  BUTTON_STYLES,
  cn,
  type DropdownOption,
} from "@equiped/ui";
import syllabusIllustration from "../../../assets/illustrations/syllabus-check.svg";
import { SyllabusModuleRow } from "../components/SyllabusModuleRow";
import { useSyllabusAlignmentList } from "../hooks/useSyllabusAlignmentList";
import type { StatusFilter } from "../utils/syllabusFiltering";

const STATUS_OPTIONS: DropdownOption<StatusFilter>[] = [
  { value: "ALL", label: "All checks" },
  {
    value: "PENDING",
    label: "Pending",
    description: "Not checked, queued, or running",
  },
  { value: "MEETS", label: "Meets syllabus" },
  { value: "PARTIALLY_MEETS", label: "Partially meets" },
  {
    value: "ATTENTION",
    label: "Needs attention",
    description: "Does not meet or check failed",
  },
];

export function SyllabusAlignmentPage() {
  const {
    page,
    setPage,
    search,
    handleSearchChange,
    statusFilter,
    handleStatusFilterChange,
    slms,
    total,
    totalPages,
    items,
  } = useSyllabusAlignmentList(10);
  const hasFilters = Boolean(search.trim()) || statusFilter !== "ALL";
  const loading = slms.isLoading && !slms.data;

  function resetFilters() {
    handleSearchChange("");
    handleStatusFilterChange("ALL");
  }

  return (
    <section
      className="mx-auto max-w-[108rem] px-4 py-6 sm:px-7 sm:py-8"
      aria-label="Syllabus checks"
    >
      <h1 className="sr-only">Syllabus check</h1>
      <div className="rounded-md border border-border bg-surface">
        <div className="flex items-center justify-between gap-6 px-5 py-5 sm:px-6 sm:py-6">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-text">Choose a module</h2>
            <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-text-muted">
              Compare its topics with a reference syllabus, or open an existing
              check.
            </p>
          </div>
          <img
            src={syllabusIllustration}
            alt=""
            className="hidden size-16 shrink-0 sm:block"
          />
        </div>

        <div className="grid gap-3 border-y border-border bg-surface-subtle/40 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_13rem] sm:px-6">
          <div className="relative min-w-0">
            <MagnifyingGlass
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            />
            <Input
              type="search"
              aria-label="Search syllabus alignments"
              placeholder="Search modules, courses, or syllabi…"
              value={search}
              onChange={(event) => handleSearchChange(event.target.value)}
              className="pl-9"
            />
          </div>
          <Dropdown
            id="syllabus-status-filter"
            aria-label="Check status"
            size="md"
            value={statusFilter}
            onChange={handleStatusFilterChange}
            options={STATUS_OPTIONS}
            containerClassName="min-w-0"
            className="w-full"
          />
        </div>

        {slms.isError ? (
          <div
            className="flex flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-6"
            role="alert"
          >
            <p className="flex items-center gap-2 text-sm text-destructive">
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              {getErrorMessage(slms.error, "Unable to load SLM documents.")}
            </p>
            <Button variant="secondary" onClick={() => void slms.refetch()}>
              Try again
            </Button>
          </div>
        ) : loading ? (
          <div
            role="status"
            aria-label="Loading modules for syllabus checks"
            className="divide-y divide-border"
          >
            {Array.from({ length: 4 }, (_, index) => (
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
          <div className="px-5 py-12 text-center sm:px-6">
            <h3 className="text-base font-semibold text-text">
              {hasFilters ? "No matching modules" : "No modules available"}
            </h3>
            <p className="mt-2 text-sm text-text-muted">
              {hasFilters
                ? "Try another search or check status."
                : "Add an SLM to your Module library to begin."}
            </p>
            {hasFilters ? (
              <Button
                variant="secondary"
                className="mt-5"
                onClick={resetFilters}
              >
                Clear filters
              </Button>
            ) : (
              <Link
                to="/documents"
                className={cn(
                  BUTTON_STYLES.base,
                  BUTTON_STYLES.variants.secondary,
                  BUTTON_STYLES.sizes.md,
                  "mt-5",
                )}
              >
                Open Module library
              </Link>
            )}
          </div>
        ) : (
          <>
            <div
              aria-hidden="true"
              className="hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_8rem] gap-6 border-b border-border px-6 py-3 text-xs font-medium text-text-muted sm:grid"
            >
              <span>Module</span>
              <span>Latest check</span>
              <span className="text-right">Action</span>
            </div>
            <ul
              aria-label="Modules for syllabus checks"
              className="divide-y divide-border"
            >
              {items.map((item) => (
                <SyllabusModuleRow key={item.document_id} item={item} />
              ))}
            </ul>
          </>
        )}

        {!loading && !slms.isError && (
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3 sm:px-6">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <p role="status" className="text-xs tabular-nums text-text-muted">
                {total === 0
                  ? "0 modules"
                  : `${(page - 1) * 10 + 1}–${Math.min(page * 10, total)} of ${total} modules`}
              </p>
              {hasFilters && items.length > 0 && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="min-h-10 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  Clear filters
                </button>
              )}
            </div>
            {totalPages > 1 && (
              <nav
                aria-label="Module pagination"
                className="flex items-center gap-2"
              >
                <Button
                  variant="secondary"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page === 1 || slms.isFetching}
                  aria-label="Previous page"
                  title="Previous page"
                >
                  <CaretLeft className="size-4" aria-hidden="true" />
                </Button>
                <span className="text-xs tabular-nums text-text-muted">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  onClick={() =>
                    setPage((value) => Math.min(totalPages, value + 1))
                  }
                  disabled={page === totalPages || slms.isFetching}
                  aria-label="Next page"
                  title="Next page"
                >
                  <CaretRight className="size-4" aria-hidden="true" />
                </Button>
              </nav>
            )}
          </footer>
        )}
      </div>
    </section>
  );
}
