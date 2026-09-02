import { Link } from '@tanstack/react-router';
import {
  ArrowsClockwise,
  CheckCircle,
  Clock,
  FolderOpen,
  Plus,
  Warning,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/Button';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import { Skeleton } from '@/shared/components/Skeleton';
import { useFacultyHome } from '../hooks/useFacultyHome';
import {
  isActiveEvaluationStatus,
  isCompletedEvaluationStatus,
  isProcessingDocument,
} from '../utils/homeData';
import { FacultyOperationalLedger } from './FacultyOperationalLedger';

export function FacultyHome() {
  const {
    isLoading,
    isError,
    error,
    homeData,
    documents,
    evaluations,
    latestEvalsByDocId,
    latestEvalsState,
    refetch,
  } = useFacultyHome();

  // Normalize documents and evaluations from either direct array or homeData
  const documentsList = documents.length > 0 ? documents : homeData.recentSlms;
  const evaluationsList = evaluations.length > 0 ? evaluations : homeData.recentEvaluations;

  // Metric Bar computations
  const totalModules = documentsList.length;
  const completedReviews = evaluationsList.filter((e) =>
    isCompletedEvaluationStatus(e.status),
  ).length;
  const inProgressCount =
    documentsList.filter((d) => isProcessingDocument(d.processingStatus)).length +
    evaluationsList.filter((e) => isActiveEvaluationStatus(e.status)).length;
  const actionRequiredCount = homeData.recentIssues.length;

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Faculty Command Ledger
          </span>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            className="h-8.5 px-3 text-xs"
            title="Refresh workspace data"
          >
            <ArrowsClockwise className="size-3.5" aria-hidden="true" />
            <span>Refresh</span>
          </Button>

          <Link
            to="/upload"
            className={BUTTON_STYLES.base + ' ' + BUTTON_STYLES.variants.primary + ' ' + BUTTON_STYLES.sizes.sm}
          >
            <Plus className="size-3.5" aria-hidden="true" weight="bold" />
            <span>Upload SLM</span>
          </Link>
        </div>
      </div>

      {/* Error state */}
      {isError ? (
        <div className="flex items-center justify-between rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-sm text-destructive" role="alert">
          <div className="flex items-center gap-2.5">
            <Warning className="size-5 shrink-0" aria-hidden="true" />
            <span className="font-semibold">
              {getErrorMessage(error, 'Unable to load workspace data.')}
            </span>
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => refetch()}
            className="h-8 px-3 text-xs"
          >
            Retry
          </Button>
        </div>
      ) : null}

      {/* Metric Ledger Strip (Single Unified Bar) */}
      <div aria-busy={isLoading} className="rounded-md border border-border bg-surface shadow-none divide-y sm:divide-y-0 sm:divide-x divide-border grid grid-cols-2 sm:grid-cols-4">
        {/* Total Modules */}
        <div className="p-4 sm:p-4.5 flex items-center gap-3.5">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <FolderOpen className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Total Modules
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-12" /> : totalModules}
            </p>
          </div>
        </div>

        {/* Completed Reviews */}
        <div className="p-4 sm:p-4.5 flex items-center gap-3.5">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-sm border border-success/30 bg-success-soft text-success shrink-0">
            <CheckCircle className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Completed Reviews
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-12" /> : completedReviews}
            </p>
          </div>
        </div>

        {/* In Progress / Ingestion */}
        <div className="p-4 sm:p-4.5 flex items-center gap-3.5">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-sm border border-info/30 bg-info-soft text-info shrink-0">
            <Clock className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              In Progress
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-12" /> : inProgressCount}
            </p>
          </div>
        </div>

        {/* Action Required */}
        <div className="p-4 sm:p-4.5 flex items-center gap-3.5">
          <div className="flex size-9 sm:size-10 items-center justify-center rounded-sm border border-warning/30 bg-warning-soft text-warning shrink-0">
            <Warning className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Action Required
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-12" /> : actionRequiredCount}
            </p>
          </div>
        </div>
      </div>

      {/* Unified Operational Module Ledger (With View Tabs) */}
      <FacultyOperationalLedger
        documents={documentsList}
        evaluations={evaluationsList}
        recentIssues={homeData.recentIssues}
        isLoading={isLoading}
        latestEvalsByDocId={latestEvalsByDocId}
        latestEvalsState={latestEvalsState}
      />
    </section>
  );
}
