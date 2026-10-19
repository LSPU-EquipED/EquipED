import type { CriterionScoreItem } from "../types";
import { EvaluationCriteriaFilters } from "./EvaluationCriteriaFilters";
import { EvaluationCriterionRow } from "./EvaluationCriterionRow";
import { getCriterionPresentation } from "../utils/criterionPresentation";
import {
  filterCriteria,
  type CriterionFilterType,
  type ScoreboardMetrics,
} from "../utils/scoreboardMetrics";

interface EvaluationCriteriaProps {
  criteria: CriterionScoreItem[];
  selectedFilter: CriterionFilterType;
  setSelectedFilter: (filter: CriterionFilterType) => void;
  metrics: ScoreboardMetrics;
}

export function EvaluationCriteria({
  criteria,
  selectedFilter,
  setSelectedFilter,
  metrics,
}: EvaluationCriteriaProps) {
  const correctedCount = criteria.filter((criterion) =>
    Boolean(criterion.reviewer_correction),
  ).length;
  const filteredCriteria = filterCriteria(criteria, selectedFilter);
  return (
    <section aria-labelledby="criteria-breakdown">
      <div className="er-criteria-toolbar">
        <h3 id="criteria-breakdown" className="er-section-title">
          Criteria breakdown
        </h3>

        {criteria.length > 0 && (
          <EvaluationCriteriaFilters
            criteriaCount={criteria.length}
            correctedCount={correctedCount}
            filteredCount={filteredCriteria.length}
            metrics={metrics}
            selectedFilter={selectedFilter}
            setSelectedFilter={setSelectedFilter}
          />
        )}
      </div>

      {criteria.length === 0 ? (
        <div className="border border-dashed border-border px-5 py-10 text-center text-sm text-text-muted">
          No criteria were returned for this specialist evaluation.
        </div>
      ) : filteredCriteria.length === 0 ? (
        <div className="border border-dashed border-border px-5 py-8 text-center text-xs text-text-muted">
          <p>No criteria match the selected filter.</p>
          <button
            type="button"
            onClick={() => setSelectedFilter("ALL")}
            className="mt-2 text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          >
            Reset filter to view all {criteria.length} criteria
          </button>
        </div>
      ) : (
        <div className="er-criteria-list divide-y divide-border">
          {filteredCriteria.map((criterion) => (
            <EvaluationCriterionRow
              key={getCriterionPresentation(criterion).code}
              criterion={criterion}
            />
          ))}
        </div>
      )}
    </section>
  );
}
