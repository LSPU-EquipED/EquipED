import { WarningCircle } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import type {
  CriterionFilterType,
  ScoreboardMetrics,
} from "../../utils/scoreboardMetrics";

interface EvaluationCriteriaFiltersProps {
  criteriaCount: number;
  correctedCount: number;
  filteredCount: number;
  metrics: Pick<ScoreboardMetrics, "attentionCount" | "strongCount">;
  selectedFilter: CriterionFilterType;
  setSelectedFilter: (filter: CriterionFilterType) => void;
}

export function EvaluationCriteriaFilters({
  criteriaCount,
  correctedCount,
  filteredCount,
  metrics: { attentionCount, strongCount },
  selectedFilter,
  setSelectedFilter,
}: EvaluationCriteriaFiltersProps) {
  return (
    <div className="er-filters" role="group" aria-label="Filter criteria">
      <button
        aria-pressed={selectedFilter === "ALL"}
        type="button"
        onClick={() => setSelectedFilter("ALL")}
        className={cn(
          "min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
          selectedFilter === "ALL"
            ? "bg-primary text-primary-foreground font-semibold"
            : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
        )}
      >
        All ({criteriaCount})
      </button>
      <button
        aria-pressed={selectedFilter === "ATTENTION"}
        type="button"
        onClick={() =>
          setSelectedFilter(
            selectedFilter === "ATTENTION" ? "ALL" : "ATTENTION",
          )
        }
        className={cn(
          "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
          selectedFilter === "ATTENTION"
            ? "bg-warning text-warning-foreground font-semibold"
            : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
        )}
      >
        {attentionCount > 0 && (
          <WarningCircle className="size-3 shrink-0" aria-hidden="true" />
        )}
        Needs attention ({attentionCount})
      </button>
      <button
        aria-pressed={selectedFilter === "STRONG"}
        type="button"
        onClick={() =>
          setSelectedFilter(selectedFilter === "STRONG" ? "ALL" : "STRONG")
        }
        className={cn(
          "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
          selectedFilter === "STRONG"
            ? "bg-success text-success-foreground font-semibold"
            : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
        )}
      >
        Strong ({strongCount})
      </button>
      {correctedCount > 0 && (
        <button
          aria-pressed={selectedFilter === "CORRECTED"}
          type="button"
          onClick={() =>
            setSelectedFilter(
              selectedFilter === "CORRECTED" ? "ALL" : "CORRECTED",
            )
          }
          className={cn(
            "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
            selectedFilter === "CORRECTED"
              ? "bg-info text-info-foreground font-semibold"
              : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
          )}
        >
          Corrected ({correctedCount})
        </button>
      )}
      {typeof selectedFilter === "number" && (
        <span className="inline-flex items-center gap-1.5 rounded-xs border border-primary/30 bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary">
          Score: {selectedFilter} ({filteredCount})
          <button
            type="button"
            onClick={() => setSelectedFilter("ALL")}
            aria-label="Clear score filter"
            className="ml-0.5 hover:text-text"
          >
            ×
          </button>
        </span>
      )}
    </div>
  );
}
