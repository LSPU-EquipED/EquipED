import { useRef } from "react";
import { ArrowsClockwise, MagnifyingGlass } from "@phosphor-icons/react";
import { Button, Input, cn } from "@equiped/ui";
import type { LedgerTab } from "../hooks/useOperationalLedger";

export interface LedgerToolbarProps {
  activeTab: LedgerTab;
  evaluationsCount: number;
  recentIssuesCount: number;
  searchQuery: string;
  panelId: string;
  onTabChange: (tab: LedgerTab) => void;
  onSearchChange: (val: string) => void;
  onRefresh?: () => void;
}

export function LedgerToolbar({
  activeTab,
  evaluationsCount,
  recentIssuesCount,
  searchQuery,
  panelId,
  onTabChange,
  onSearchChange,
  onRefresh,
}: LedgerToolbarProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const tabs: { id: LedgerTab; label: string; count: number }[] = [
    { id: "evaluations", label: "Recent evaluations", count: evaluationsCount },
    { id: "attention", label: "Requires review", count: recentIssuesCount },
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-t-md border-b border-border bg-surface px-4 py-4 sm:px-6">
      <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-3">
        <h2 className="text-sm font-semibold text-text">
          Recent evaluation activity
        </h2>
        <div
          role="tablist"
          aria-label="Ledger views"
          className="flex flex-wrap gap-1"
        >
          {tabs.map((tab, index) => (
            <button
              key={tab.id}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              id={`${panelId}-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={panelId}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(event) => {
                let nextIndex: number;
                if (event.key === "ArrowRight")
                  nextIndex = (index + 1) % tabs.length;
                else if (event.key === "ArrowLeft")
                  nextIndex = (index + tabs.length - 1) % tabs.length;
                else if (event.key === "Home") nextIndex = 0;
                else if (event.key === "End") nextIndex = tabs.length - 1;
                else return;
                event.preventDefault();
                onTabChange(tabs[nextIndex].id);
                tabRefs.current[nextIndex]?.focus();
              }}
              className={cn(
                "inline-flex min-h-10 items-center gap-2 rounded-sm px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                activeTab === tab.id
                  ? "bg-primary-soft text-primary"
                  : "text-text-muted hover:bg-surface-subtle hover:text-text",
              )}
            >
              {tab.label}{" "}
              <span className="text-xs tabular-nums">{tab.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex w-full items-center gap-2 sm:w-auto">
        <div className="relative min-w-0 flex-1 sm:w-56">
          <MagnifyingGlass
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <Input
            type="search"
            aria-label={
              activeTab === "evaluations"
                ? "Search evaluations"
                : "Search review items"
            }
            placeholder={
              activeTab === "evaluations"
                ? "Search evaluations…"
                : "Search review items…"
            }
            value={searchQuery}
            onChange={(event) => onSearchChange(event.target.value)}
            className="pl-9"
          />
        </div>
        {onRefresh && (
          <Button
            type="button"
            variant="secondary"
            onClick={onRefresh}
            aria-label="Refresh workspace data"
            title="Refresh workspace data"
            className="w-10 shrink-0 px-0"
          >
            <ArrowsClockwise className="size-4" aria-hidden="true" />
          </Button>
        )}
      </div>
    </div>
  );
}
