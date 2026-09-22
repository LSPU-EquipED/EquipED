import {
  ArrowsClockwise,
  MagnifyingGlass,
} from "@phosphor-icons/react";
import { Button, cn } from "@equiped/ui";
import type { LedgerTab } from "../hooks/useOperationalLedger";

export interface LedgerToolbarProps {
  activeTab: LedgerTab;
  evaluationsCount: number;
  recentIssuesCount: number;
  searchQuery: string;
  onTabChange: (tab: LedgerTab) => void;
  onSearchChange: (val: string) => void;
  onRefresh?: () => void;
}

export function LedgerToolbar({
  activeTab,
  evaluationsCount,
  recentIssuesCount,
  searchQuery,
  onTabChange,
  onSearchChange,
  onRefresh,
}: LedgerToolbarProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-3">
      {/* Left: Section Stamp & Unified Segment Switcher */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-bold text-text tracking-tight shrink-0 select-none">
          Recent evaluation activity
        </span>

        <div
          className="hidden sm:block h-4 w-px bg-border shrink-0"
          aria-hidden="true"
        />

        <div
          role="tablist"
          aria-label="Ledger views"
          className="flex items-center gap-1 rounded-sm bg-surface-subtle p-1 border border-border/60"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "evaluations"}
            onClick={() => onTabChange("evaluations")}
            className={cn(
              "flex items-center gap-2 rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer select-none",
              activeTab === "evaluations"
                ? "bg-surface text-primary font-bold shadow-xs border border-border/80"
                : "text-text-muted hover:text-text",
            )}
          >
            <span>Recent Evaluations</span>
            <span
              className={cn(
                "rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold",
                activeTab === "evaluations"
                  ? "bg-primary-soft text-primary"
                  : "bg-surface text-text-muted",
              )}
            >
              {evaluationsCount}
            </span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "attention"}
            onClick={() => onTabChange("attention")}
            className={cn(
              "flex items-center gap-2 rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer select-none",
              activeTab === "attention"
                ? "bg-surface text-warning font-bold shadow-xs border border-border/80"
                : "text-text-muted hover:text-text",
            )}
          >
            <span>Requires Review</span>
            <span
              className={cn(
                "rounded-xs px-1.5 py-0.2 text-[10px] tabular-nums font-bold",
                activeTab === "attention"
                  ? "bg-warning-soft text-warning"
                  : "bg-surface text-text-muted",
              )}
            >
              {recentIssuesCount}
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
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
    </div>
  );
}
