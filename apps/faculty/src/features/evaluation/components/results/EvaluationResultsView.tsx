import { EvaluationCriteria } from "./EvaluationCriteria";
import { EvaluationScoreSummary } from "./EvaluationScoreSummary";
import {
  EvaluationResultMetadata,
  EvaluationRecordMetadata,
} from "./EvaluationResultMetadata";
import { useState, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, ArrowsClockwise, NotePencil } from "@phosphor-icons/react";
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
} from "../../types";
import { SpecialistExportDownloadButton } from "../exports/ExportDocument";
import { sortCriteriaGrouped } from "../../utils/scoreHelpers";

import { formatEvaluationDateTime } from "../../utils/dateFormatting";
import {
  calculateScoreboardMetrics,
  type CriterionFilterType,
} from "../../utils/scoreboardMetrics";
import { buildEvaluationResultExport } from "../../utils/evaluationResultExport";
import "../../styles/evaluation-results.css";

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
    <div className="er-results">
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
      <header className="er-header">
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
          <h2 className="er-title">{displayTitle}</h2>
          <p className="er-context">
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
        <div className="er-actions flex max-w-full flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={
              !domainScore ||
              domainScore.status === "HISTORICAL_UNSCORED" ||
              domainScore.status === "ERROR"
            }
            onClick={onOpenReviewModal}
            className="gap-1.5 text-xs font-semibold"
          >
            <NotePencil className="size-3.5" aria-hidden="true" />
            Review scores
          </Button>
          {domainScore ? (
            <SpecialistExportDownloadButton
              domainData={buildEvaluationResultExport({
                agentId: validAgent,
                evaluationId,
                results,
                domainScore,
                criteria,
                activeItem,
                activeDocument,
              })}
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

      {results.evaluation_status === "FAILED" && (
        <p
          role="alert"
          className="border border-destructive/30 bg-destructive-soft p-4 text-sm text-destructive"
        >
          Evaluation failed. Available findings are diagnostic only.
        </p>
      )}

      <EvaluationResultMetadata
        courseTitle={activeDocument?.courseTitle}
        uploadedAt={activeItem?.uploaded_at || activeDocument?.uploadedAt}
        rubricVersion={domainScore.version}
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

        {results.legacy_notice && (
          <p className="border-b border-border py-3 text-xs text-text-muted">
            {results.legacy_notice}
          </p>
        )}
        <EvaluationCriteria
          criteria={criteria}
          selectedFilter={selectedFilter}
          setSelectedFilter={setSelectedFilter}
          metrics={metrics}
        />
        {validAgent === "coordinator" && domainScore.advisory_outputs && (
          <div className="er-advisory">
            <CurriculumAlignmentSupplement
              advisory={domainScore.advisory_outputs}
            />
          </div>
        )}
        <EvaluationRecordMetadata
          evaluationId={evaluationId}
          formSnapshotId={domainScore.form_snapshot_id}
        />
      </section>
    </div>
  );
}
