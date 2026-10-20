import { CaretDown, WarningCircle } from "@phosphor-icons/react";
import { useId, useState } from "react";
import { cn } from "@equiped/ui";
import type { CriterionScoreItem } from "../types";
import {
  cleanJustification,
  boundNarrative,
  formatEvidenceText,
  formatScore,
} from "../utils/scoreHelpers";
import {
  getCriterionPresentation,
  getMissingEvidenceNote,
  getAdvisoryEvidenceStatus,
} from "../utils/criterionPresentation";

export function EvaluationCriterionRow({
  criterion,
}: {
  criterion: CriterionScoreItem;
}) {
  const { code, pageNumber, criterionText } =
    getCriterionPresentation(criterion);
  const [showFullFinding, setShowFullFinding] = useState(false);
  const findingId = useId();
  const finding = cleanJustification(criterion.justification);
  const preview = code.startsWith("ITSO-")
    ? finding
    : boundNarrative(finding, 420);
  const evidence = formatEvidenceText(criterion.evidence);
  const evidenceStatus = getAdvisoryEvidenceStatus(criterion);
  const needsEvidenceCheck = Boolean(
    criterion.is_ungrounded && !evidenceStatus,
  );
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
            {(needsEvidenceCheck ||
              evidenceStatus ||
              criterion.reviewer_correction) && (
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {needsEvidenceCheck && (
                  <span className="inline-flex items-center gap-1 text-warning">
                    <WarningCircle className="size-3.5" aria-hidden="true" />
                    Check evidence
                  </span>
                )}
                {evidenceStatus && (
                  <span
                    className={
                      evidenceStatus === "rights_unverified"
                        ? "text-warning"
                        : "text-info"
                    }
                  >
                    {evidenceStatus === "rights_unverified"
                      ? "Rights unverified"
                      : "No concern detected in reviewed text"}
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
              criterion.score == null
                ? "border-border bg-surface-subtle text-text-muted"
                : criterion.score >= 3
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
          <p id={findingId} className="er-finding-copy">
            {(showFullFinding ? finding : preview) ||
              "No specialist finding was returned."}
          </p>
          {preview !== finding && (
            <button
              type="button"
              aria-expanded={showFullFinding}
              aria-controls={findingId}
              onClick={() => setShowFullFinding(!showFullFinding)}
              className="mt-2 text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              {showFullFinding
                ? "Show less"
                : "Show full finding and source checks"}
            </button>
          )}
          {(criterion.public_sources?.length ||
            criterion.reference_check_note) && (
            <div className="mt-4 space-y-3">
              <p className="er-label">Source checks</p>
              {criterion.reference_check_note && (
                <p className="text-sm leading-relaxed text-text-muted">
                  {criterion.reference_check_note}
                </p>
              )}
              {criterion.public_sources?.map((source) => (
                <div key={source.number} className="min-w-0">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-words text-sm font-semibold text-primary underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    Source {source.number}: {source.title || source.url}
                  </a>
                  <div
                    className="er-evidence-scroll mt-2"
                    role="region"
                    aria-label={`${code} source ${source.number} passage`}
                    tabIndex={0}
                  >
                    <blockquote>{source.excerpt}</blockquote>
                  </div>
                </div>
              ))}
            </div>
          )}
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
          {evidence ? (
            <div
              className="er-evidence-scroll"
              role="region"
              aria-label={`${code} SLM evidence`}
              tabIndex={0}
            >
              <blockquote>&ldquo;{evidence}&rdquo;</blockquote>
            </div>
          ) : (
            <p className="mt-2 text-sm text-text-muted">
              {getMissingEvidenceNote(criterion)}
            </p>
          )}
          {needsEvidenceCheck && (
            <p className="mt-3 text-xs font-medium text-warning">
              Evidence requires reviewer confirmation.
            </p>
          )}
        </div>
      </div>
    </details>
  );
}
