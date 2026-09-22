import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  CheckCircle,
  MagnifyingGlass,
  X,
} from "@phosphor-icons/react";
import { Badge, cn } from "@equiped/ui";
import type { DeskQueueItem } from "../types";

export interface SelectModuleModalProps {
  agentId: string;
  items: DeskQueueItem[];
  onClose: () => void;
}

import { formatDateWithFallback } from "../utils/dateFormatting";

export function SelectModuleModal({
  agentId,
  items,
  onClose,
}: SelectModuleModalProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProgram, setSelectedProgram] = useState<string>("ALL");
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Filter only items that are NOT evaluated yet (strictly unevaluated/ready/failed retryable)
  const unevaluated = useMemo(() => {
    return items.filter(
      (i) =>
        !i.my_status ||
        ["PENDING", "READY", "FAILED"].includes(i.my_status.toUpperCase()),
    );
  }, [items]);

  const hasModules = unevaluated.length > 0;

  // Extract distinct programs for quick-filter chips
  const availablePrograms = useMemo(() => {
    const progs = new Set<string>();
    unevaluated.forEach((item) => {
      if (item.program) progs.add(item.program);
    });
    return Array.from(progs).sort();
  }, [unevaluated]);

  // Filter by search query and program
  const filtered = useMemo(() => {
    return unevaluated.filter((i) => {
      const matchesProgram =
        selectedProgram === "ALL" ||
        (i.program &&
          i.program.toLowerCase() === selectedProgram.toLowerCase());

      if (!matchesProgram) return false;
      if (!searchQuery.trim()) return true;

      const term = searchQuery.toLowerCase().trim();
      return (
        i.title.toLowerCase().includes(term) ||
        (i.course_code || "").toLowerCase().includes(term) ||
        (i.program || "").toLowerCase().includes(term)
      );
    });
  }, [unevaluated, searchQuery, selectedProgram]);

  // Accessibility: Escape key listener
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Focus search input on mount if modules exist
  useEffect(() => {
    if (hasModules) {
      searchInputRef.current?.focus();
    }
  }, [hasModules]);

  const handleSelectModule = (documentId: string) => {
    navigate({
      to: "/specialists/$agentId/$documentId",
      params: { agentId, documentId },
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto overflow-x-hidden p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-description"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-surface-base/75 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Card */}
      <div
        className="relative z-10 flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-md border border-border bg-surface shadow-lg transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="min-w-0 space-y-1.5">
            <p className="text-[11px] font-semibold text-primary">
              Module selection
            </p>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2
                id="modal-title"
                className="text-base font-semibold text-text sm:text-lg"
              >
                Choose an unevaluated module
              </h2>
              {hasModules && (
                <Badge variant="neutral" className="text-xs font-semibold">
                  {unevaluated.length} ready
                </Badge>
              )}
            </div>
            <p
              id="modal-description"
              className="max-w-xl text-xs leading-relaxed text-text-muted"
            >
              {hasModules
                ? "Select a course module from storage to start this specialist desk review."
                : "Every course module in storage has already been reviewed by this desk."}
            </p>
          </div>

          <button
            onClick={onClose}
            type="button"
            aria-label="Close dialog"
            className="inline-flex size-8 items-center justify-center rounded-sm border border-border/70 text-text-muted hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors cursor-pointer shrink-0"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        {/* Search & Filter Controls (Rendered ONLY when modules exist) */}
        {hasModules && (
          <div className="shrink-0 space-y-3 border-b border-border bg-surface-subtle/35 px-5 pb-4 pt-4 sm:px-6">
            <div className="relative w-full">
              <MagnifyingGlass
                className="size-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
                aria-hidden="true"
              />
              <input
                ref={searchInputRef}
                type="text"
                aria-label="Search unevaluated modules"
                placeholder="Search by title, course code, or program"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9.5 w-full rounded-sm border border-input bg-surface pl-10 pr-10 text-xs sm:text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text p-1 rounded-sm"
                  aria-label="Clear search"
                >
                  <X className="size-3.5" />
                </button>
              )}
            </div>

            {/* Quick-filter Chips by Program */}
            {availablePrograms.length > 1 && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-xs">
                <span className="mr-1 shrink-0 font-medium text-text-muted">
                  Program
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedProgram("ALL")}
                  className={cn(
                    "shrink-0 cursor-pointer rounded-sm px-2.5 py-1 text-xs font-medium transition-colors",
                    selectedProgram === "ALL"
                      ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                      : "bg-surface-subtle text-text-muted hover:text-text hover:bg-surface-subtle/80 border border-border/60",
                  )}
                >
                  All Programs ({unevaluated.length})
                </button>
                {availablePrograms.map((prog) => (
                  <button
                    key={prog}
                    type="button"
                    onClick={() => setSelectedProgram(prog)}
                    className={cn(
                      "shrink-0 cursor-pointer rounded-sm px-2.5 py-1 text-xs font-medium transition-colors",
                      selectedProgram === prog
                        ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "bg-surface-subtle text-text-muted hover:text-text hover:bg-surface-subtle/80 border border-border/60",
                    )}
                  >
                    {prog}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal Body / Module List */}
        <div className="min-h-[220px] flex-1 space-y-3 overflow-y-auto p-5 sm:p-6">
          {!hasModules ? (
            /* Simplified Empty State (No search or result controls) */
            <div className="flex flex-col items-center justify-center space-y-3.5 px-4 py-10 text-center">
              <div className="flex size-11 items-center justify-center rounded-sm border border-success/25 bg-success-soft text-success">
                <CheckCircle className="size-5" weight="bold" />
              </div>
              <div className="space-y-1 max-w-sm">
                <h3 className="text-sm font-semibold text-text">
                  Desk queue is clear
                </h3>
                <p className="text-xs leading-relaxed text-text-muted">
                  All learning modules currently in storage have been evaluated
                  for this specialist desk. New uploads will appear here when
                  ready.
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="mt-1 h-9 cursor-pointer rounded-sm border border-border bg-surface px-5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle"
              >
                Close
              </button>
            </div>
          ) : filtered.length === 0 ? (
            /* No search match state */
            <div className="space-y-3 py-12 text-center">
              <p className="text-xs text-text-muted sm:text-sm">
                No matching modules found for &ldquo;
                <span className="font-semibold text-text">{searchQuery}</span>
                &rdquo;
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedProgram("ALL");
                }}
                className="cursor-pointer text-xs font-semibold text-primary hover:underline"
              >
                Clear filters
              </button>
            </div>
          ) : (
            /* Filtered Module List */
            <div className="divide-y divide-border border-y border-border">
              {filtered.map((item) => (
                <button
                  key={item.document_id}
                  onClick={() => handleSelectModule(item.document_id)}
                  type="button"
                  className="group flex min-h-[68px] w-full cursor-pointer items-center justify-between gap-4 px-3 py-3 text-left transition-colors hover:bg-primary-soft/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:px-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                      {item.course_code && (
                        <span className="font-mono font-semibold text-text">
                          {item.course_code}
                        </span>
                      )}
                      {item.program && (
                        <span className="text-text-muted">{item.program}</span>
                      )}
                      <span className="inline-flex items-center gap-1.5 font-medium text-info">
                        <span className="size-1.5 rounded-full bg-info" />
                        Ready
                      </span>
                    </div>
                    <h3 className="mt-1 truncate text-sm font-semibold text-text transition-colors group-hover:text-primary">
                      {item.title}
                    </h3>
                    <p className="mt-0.5 text-xs text-text-muted">
                      Uploaded {formatDateWithFallback(item.uploaded_at, "Recent")}
                    </p>
                  </div>
                  <span className="flex shrink-0 items-center gap-1.5 text-xs font-semibold text-primary transition-transform group-hover:translate-x-0.5">
                    <span className="hidden sm:inline">Select</span>
                    <ArrowRight className="size-3.5" weight="bold" />
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex shrink-0 items-center justify-between border-t border-border bg-surface-subtle/30 px-5 py-3 text-xs text-text-muted sm:px-6">
          <span className="text-[11px]">
            Press{" "}
            <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border font-mono text-[10px]">
              Esc
            </kbd>{" "}
            to exit
          </span>

          <div className="flex items-center gap-3">
            {hasModules && (
              <span className="text-[11px] hidden sm:inline">
                {filtered.length} of {unevaluated.length} module
                {unevaluated.length === 1 ? "" : "s"} shown
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
