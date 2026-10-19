import { CaretDown, WarningCircle } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import type { CriterionScoreItem } from "../types";
import {
  cleanJustification,
  formatEvidenceText,
  formatScore,
} from "../utils/scoreHelpers";
import { getCriterionPresentation } from "../utils/criterionPresentation";

export function EvaluationCriterionRow({
  criterion,
}: {
  criterion: CriterionScoreItem;
}) {
  const { code, pageNumber, criterionText } =
    getCriterionPresentation(criterion);
  return (
    <details className="group/criterion min-w-0 bg-surface">
      <summary className="grid min-h-12 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3 py-3 hover:bg-surface-subtle/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring sm:px-4 [&::-webkit-details-marker]:hidden">
        <div className="flex min-w-0 items-start gap-2.5">
          <CaretDown
            className="mt-0.5 size-3.5 shrink-0 -rotate-90 text-text-muted group-open/criterion:rotate-0"
            aria-hidden="true"
          />
          <span className="er-criterion-code font-mono">{code}</span>
          <div className="min-w-0">
            <h4 className="er-criterion-title">{criterionText}</h4>
            {criterion.description && (
              <p className="er-criterion-description">
                {criterion.description}
              </p>
            )}
            {(criterion.is_ungrounded || criterion.reviewer_correction) && (
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {criterion.is_ungrounded && (
                  <span className="inline-flex items-center gap-1 text-warning">
                    <WarningCircle className="size-3.5" aria-hidden="true" />
                    Check evidence
                  </span>
                )}
                {criterion.reviewer_correction && (
                  <span className="text-info">Reviewer correction</span>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="sr-only">Generated score</span>
          <span
            className={cn(
              "inline-flex items-center rounded-xs border px-2.5 py-1 font-mono text-xs font-semibold",
              (criterion.score ?? 0) >= 3
                ? "border-success/30 bg-success-soft text-success"
                : "border-warning/30 bg-warning-soft text-warning",
            )}
          >
            {formatScore(criterion.score)} / 4
          </span>
        </div>
      </summary>

      <div className="er-criterion-content">
        <div className="er-finding">
          <p className="er-label">Specialist finding</p>
          <p className="er-finding-copy">
            {criterion.justification
              ? cleanJustification(criterion.justification)
              : "No specialist finding was returned."}
          </p>
          {criterion.reviewer_correction && (
            <div className="er-correction">
              <p className="font-semibold text-info">
                {criterion.reviewer_correction.action === "REJECT"
                  ? "Finding rejected by reviewer"
                  : "Reviewer correction"}
              </p>
              {criterion.reviewer_correction.score != null && (
                <p className="mt-1 font-mono font-semibold text-text">
                  Override score:{" "}
                  {formatScore(criterion.reviewer_correction.score)} / 4
                </p>
              )}
              {criterion.reviewer_correction.justification && (
                <p className="mt-1 leading-relaxed text-text-muted">
                  {cleanJustification(
                    criterion.reviewer_correction.justification,
                  )}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="er-evidence">
          <div className="flex items-center justify-between gap-2">
            <p className="er-label">SLM evidence</p>
            {Boolean(pageNumber) && (
              <span className="text-xs text-text-muted">Page {pageNumber}</span>
            )}
          </div>
          {criterion.evidence ? (
            <div
              className="er-evidence-scroll"
              role="region"
              aria-label={`${code} SLM evidence`}
              tabIndex={0}
            >
              <blockquote>
                &ldquo;{formatEvidenceText(criterion.evidence)}&rdquo;
              </blockquote>
            </div>
          ) : (
            <p className="mt-2 text-sm text-text-muted">
              No quoted evidence was returned.
            </p>
          )}
          {criterion.is_ungrounded && (
            <p className="mt-3 text-xs font-medium text-warning">
              Evidence requires reviewer confirmation.
            </p>
          )}
        </div>
      </div>
    </details>
  );
}
