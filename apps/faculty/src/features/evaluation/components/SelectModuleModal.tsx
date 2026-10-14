import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  FileText,
  MagnifyingGlass,
  X,
} from "@phosphor-icons/react";
import { Button, Dropdown, cn } from "@equiped/ui";
import { isTargetAgent, TARGET_AGENT_META } from "@equiped/types";
import type { DeskQueueItem } from "../types";
import { formatDateWithFallback } from "../utils/dateFormatting";
import { specialistModuleState } from "../utils/specialistModuleState";

export interface SelectModuleModalProps {
  agentId: string;
  items: DeskQueueItem[];
  onClose: () => void;
}

export function SelectModuleModal({
  agentId,
  items,
  onClose,
}: SelectModuleModalProps) {
  const navigate = useNavigate();
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [program, setProgram] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const desk = isTargetAgent(agentId)
    ? TARGET_AGENT_META[agentId].shortLabel
    : "specialist";
  const programs = useMemo(
    () =>
      [
        ...new Set(
          items.flatMap((item) => (item.program ? [item.program] : [])),
        ),
      ].sort(),
    [items],
  );
  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();
    return items.filter(
      (item) =>
        (program === "ALL" || item.program === program) &&
        (status === "ALL" ||
          specialistModuleState(item.my_status).status === status) &&
        [item.title, item.course_code, item.program].some((value) =>
          value?.toLowerCase().includes(term),
        ),
    );
  }, [items, program, search, status]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    searchInputRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus();
    };
  }, []);

  const selectModule = (documentId: string) => {
    void navigate({
      to: "/specialists/$agentId/$documentId",
      params: { agentId, documentId },
    });
    onClose();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay/50 p-3 sm:p-6"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="flex max-h-[85dvh] w-full max-w-4xl flex-col overflow-hidden rounded-md border border-border bg-surface shadow-lg animate-ledger-modal-in"
        onKeyDown={(event) => {
          if (event.defaultPrevented) return;
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          }
          if (event.key === "Tab") {
            const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
              'button:not([disabled]), input:not([disabled]), [tabindex="0"]',
            );
            if (!focusable?.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 px-5 py-5 sm:px-6">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-text">
              Select module
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-text-muted">
              Open an SLM in the {desk} workspace.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close module selection"
            className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="grid shrink-0 grid-cols-2 gap-3 border-y border-border bg-surface-subtle/40 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_9rem_10rem] sm:px-6">
          <div className="relative col-span-2 min-w-0 sm:col-span-1">
            <MagnifyingGlass
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            />
            <input
              ref={searchInputRef}
              type="search"
              aria-label="Search modules"
              placeholder="Search by module or course"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-3 text-sm text-text placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-ring"
            />
          </div>
          <Dropdown
            aria-label="Filter modules by program"
            value={program}
            onChange={setProgram}
            options={[
              { value: "ALL", label: "All programs" },
              ...programs.map((value) => ({ value, label: value })),
            ]}
            containerClassName="min-w-0 w-full"
            size="md"
            className="h-10 w-full"
          />
          <Dropdown
            aria-label="Filter modules by status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "ALL", label: "All statuses" },
              { value: "COMPLETED", label: "Completed" },
              { value: "READY", label: "Not evaluated" },
              { value: "EVALUATING", label: "Evaluating" },
              { value: "FAILED", label: "Failed" },
            ]}
            containerClassName="min-w-0 w-full"
            size="md"
            className="h-10 w-full"
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {filteredItems.length ? (
            <ul className="divide-y divide-border px-5 sm:px-6">
              {filteredItems.map((item) => {
                const state = specialistModuleState(item.my_status);
                return (
                  <li key={item.document_id}>
                    <button
                      type="button"
                      onClick={() => selectModule(item.document_id)}
                      className="group flex w-full cursor-pointer items-center gap-3 rounded-sm px-1 py-5 text-left transition-colors hover:bg-primary-soft/40 focus-visible:outline-2 focus-visible:outline-ring sm:gap-4 sm:px-2"
                    >
                      <span className="hidden size-10 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text-muted sm:flex">
                        <FileText className="size-5" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="break-words text-sm font-semibold leading-snug text-text group-hover:text-primary">
                          {item.title}
                        </h3>
                        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
                          {[item.course_code, item.program]
                            .filter(Boolean)
                            .join(" · ")}
                          <span className="hidden sm:inline">
                            {item.course_code || item.program ? "· " : ""}
                            Uploaded{" "}
                            {formatDateWithFallback(
                              item.uploaded_at,
                              "date unavailable",
                            )}
                          </span>
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2 sm:min-w-36">
                        <span
                          className={cn("text-xs font-medium", state.color)}
                        >
                          {state.label}
                        </span>
                        <span className="flex items-center gap-2 text-xs font-semibold text-primary">
                          {state.action}
                          <ArrowRight className="size-3.5" aria-hidden="true" />
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="px-6 py-14 text-center">
              <FileText
                className="mx-auto size-6 text-text-muted"
                aria-hidden="true"
              />
              <h3 className="mt-3 text-sm font-semibold text-text">
                {items.length ? "No matching modules" : "No modules available"}
              </h3>
              <p className="mt-2 text-sm text-text-muted">
                {items.length
                  ? "Try a different search, program, or status."
                  : "Processed SLMs from Module Library will appear here."}
              </p>
              {items.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-4"
                  onClick={() => {
                    setSearch("");
                    setProgram("ALL");
                    setStatus("ALL");
                  }}
                >
                  Clear filters
                </Button>
              )}
            </div>
          )}
        </div>
        <footer className="flex shrink-0 items-center justify-between gap-3 border-t border-border px-5 py-3 sm:px-6">
          <p role="status" className="text-xs tabular-nums text-text-muted">
            {filteredItems.length} of {items.length} modules
          </p>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
