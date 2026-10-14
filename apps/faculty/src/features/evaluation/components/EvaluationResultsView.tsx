import { EvaluationCriteria } from "./EvaluationCriteria";
import { EvaluationScoreSummary } from "./EvaluationScoreSummary";
import { EvaluationResultMetadata } from "./EvaluationResultMetadata";
import { useState, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowsClockwise,
  CaretDown,
  NotePencil,
} from "@phosphor-icons/react";
import { Button, CurriculumAlignmentSupplement } from "@equiped/ui";
import type {
  TargetAgentMeta,
  TargetAgent,
  ClientDocument,
} from "@equiped/types";
import type {
  DeskQueueItem,
  DomainScoreBlock,
  EvaluationResponse,
  EvaluationResultsResponse,
} from "../types";
import { SpecialistExportDownloadButton } from "./ExportDocument";
import { sortCriteriaGrouped } from "../utils/scoreHelpers";

import { formatEvaluationDateTime } from "../utils/dateFormatting";
import {
  calculateScoreboardMetrics,
  type CriterionFilterType,
} from "../utils/scoreboardMetrics";

export interface EvaluationResultsViewProps {
  results: EvaluationResultsResponse;
  domainScore: DomainScoreBlock;
  evaluation: Pick<
    EvaluationResponse,
    "evaluation_id" | "document_id" | "submitted_at"
  > & { completed_at?: string | null };
  context?: "workspace" | "history";
  newerEvaluationId?: string;
  meta: TargetAgentMeta;
  validAgent: TargetAgent;
  activeItem: DeskQueueItem | null;
  activeDocument: ClientDocument | null;
  onOpenReviewModal: () => void;
  onOpenReevaluateModal: () => void;
}

export function EvaluationResultsView({
  results,
  domainScore,
  meta,
  validAgent,
  activeItem,
  activeDocument,
  evaluation,
  context = "workspace",
  newerEvaluationId,
  onOpenReviewModal,
  onOpenReevaluateModal,
}: EvaluationResultsViewProps) {
  const [selectedFilter, setSelectedFilter] =
    useState<CriterionFilterType>("ALL");
  const criteria = useMemo(
    () =>
      sortCriteriaGrouped(domainScore.criteria, results.forms?.[validAgent]),
    [domainScore.criteria, results.forms, validAgent],
  );
  const displayTitle =
    results.document_title ||
    activeDocument?.lessonTitle ||
    activeDocument?.courseTitle ||
    activeItem?.title ||
    activeDocument?.title ||
    "Course Module";
  const courseCode =
    activeItem?.course_code || activeDocument?.courseCode || "";
  const program =
    results.program || activeItem?.program || activeDocument?.program || "";
  const evaluationId = evaluation.evaluation_id;
  const maxScore = domainScore?.max_score || 4;
  const metrics = useMemo(
    () => calculateScoreboardMetrics(criteria),
    [criteria],
  );
  const evaluatedAt = results.completed_at || evaluation.completed_at;
  const runDate = evaluatedAt || evaluation.submitted_at;
  const hasCorrections = criteria.some(
    (criterion) => criterion.reviewer_correction,
  );

  return (
    <div className="min-w-0">
      {newerEvaluationId && (
        <div
          role="status"
          className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3 text-sm text-text-muted"
        >
          <span>
            You are viewing an earlier evaluation. A newer run is available.
          </span>
          <Link
            to="/evaluations/$id"
            params={{ id: newerEvaluationId }}
            className="font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          >
            View latest run
          </Link>
        </div>
      )}
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border pb-3">
        <div className="min-w-0 flex-1 basis-72">
          {context === "history" ? (
            <Link
              to="/evaluations"
              className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              Back to evaluation history
            </Link>
          ) : (
            <Link
              to="/specialists/$agentId"
              params={{ agentId: validAgent }}
              className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              Back to {meta.shortLabel} workspace
            </Link>
          )}
          <h2 className="break-words text-lg font-semibold leading-snug text-text [overflow-wrap:anywhere]">
            {displayTitle}
          </h2>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-relaxed text-text-muted">
            <span>
              {[`${meta.shortLabel} review`, courseCode, program]
                .filter(Boolean)
                .join(" · ")}
            </span>
            {runDate && (
              <time dateTime={runDate}>
                <span aria-hidden="true" className="mr-2 hidden sm:inline">
                  ·
                </span>
                {evaluatedAt ? "Evaluated" : "Submitted"}{" "}
                {formatEvaluationDateTime(runDate)}
              </time>
            )}
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={!domainScore}
            onClick={onOpenReviewModal}
            className="gap-1.5 text-xs font-semibold"
          >
            <NotePencil className="size-3.5" aria-hidden="true" />
            Review scores
          </Button>
          {domainScore ? (
            <SpecialistExportDownloadButton
              domainData={{
                agentId: validAgent,
                documentTitle:
                  results.document_title ||
                  activeItem?.title ||
                  activeDocument?.title ||
                  "Course Module",
                program:
                  results.program ||
                  activeItem?.program ||
                  activeDocument?.program ||
                  null,
                courseCode:
                  activeItem?.course_code || activeDocument?.courseCode || null,
                evaluationId,
                isPartial: results.is_partial,
                partialReason: results.partial_reason,
                evaluationStatus: results.evaluation_status,
                criteria,
                subtotal: domainScore.subtotal,
                max_score: maxScore,
                status:
                  domainScore.status ||
                  results.evaluation_status ||
                  "COMPLETED",
                adjectival_rating: domainScore.adjectival_rating ?? undefined,
                summary: domainScore.summary,
                version: domainScore.version,
                form_snapshot_id: domainScore.form_snapshot_id ?? undefined,
                results,
                document: activeDocument ?? null,
              }}
              agentId={validAgent}
              variant="secondary"
            />
          ) : null}

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onOpenReevaluateModal}
            aria-label="Re-evaluate"
            title="Re-evaluate"
            className="size-9 shrink-0 p-0"
          >
            <ArrowsClockwise className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </header>

      <div className="grid min-w-0 gap-4 pt-4 xl:grid-cols-[14rem_minmax(0,1fr)] xl:gap-6">
        <EvaluationResultMetadata
          evaluationId={evaluationId}
          courseTitle={activeDocument?.courseTitle}
          uploadedAt={activeItem?.uploaded_at || activeDocument?.uploadedAt}
          rubricVersion={domainScore.version}
          formSnapshotId={domainScore.form_snapshot_id}
          requiresCurriculum={meta.requiresCurriculum}
        />

        <section className="min-w-0" aria-label="Evaluation results">
          <EvaluationScoreSummary
            domainScore={domainScore}
            meta={meta}
            metrics={metrics}
            selectedFilter={selectedFilter}
            setSelectedFilter={setSelectedFilter}
            hasCorrections={hasCorrections}
          />

          {domainScore?.summary && (
            <details className="group/summary border-b border-border py-2">
              <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2 text-xs font-medium text-text-muted focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                <CaretDown
                  className="size-3.5 -rotate-90 group-open/summary:rotate-0"
                  aria-hidden="true"
                />
                Specialist summary
              </summary>
              <p className="pb-2 pt-1 text-sm leading-relaxed text-text [overflow-wrap:anywhere]">
                {domainScore.summary}
              </p>
            </details>
          )}

          {results.legacy_notice && (
            <p className="border-b border-border py-3 text-xs text-text-muted">
              {results.legacy_notice}
            </p>
          )}
          {validAgent === "coordinator" && domainScore?.advisory_outputs && (
            <CurriculumAlignmentSupplement
              advisory={domainScore.advisory_outputs}
            />
          )}

          <EvaluationCriteria
            criteria={criteria}
            selectedFilter={selectedFilter}
            setSelectedFilter={setSelectedFilter}
            metrics={metrics}
          />
        </section>
      </div>
    </div>
  );
}
