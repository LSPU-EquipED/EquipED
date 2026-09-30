import {
  ArrowsClockwise,
  CheckCircle,
  Play,
  Spinner,
  UploadSimple,
  Warning,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';

export function ValidationLaunchReadiness({
  form,
  enteredScoreCount,
  totalCriteriaCount,
}: {
  form: Pick<
    ModelValidationFormState,
    | 'file'
    | 'title'
    | 'program'
    | 'uploaded'
    | 'criterionCatalog'
    | 'uploadMutation'
    | 'validationMutation'
    | 'allCriterionScoresComplete'
    | 'uploadedProcessingStatus'
    | 'uploadedDocumentReady'
    | 'canSubmitEvaluation'
    | 'error'
    | 'isStaleBinding'
    | 'handleReloadCatalog'
    | 'resetPreparedUpload'
    | 'handleStart'
  >;
  enteredScoreCount: number;
  totalCriteriaCount: number;
}) {
  const {
    file,
    title,
    program,
    uploaded,
    criterionCatalog,
    uploadMutation,
    validationMutation,
    allCriterionScoresComplete,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    canSubmitEvaluation,
    error,
    isStaleBinding,
    handleReloadCatalog,
    resetPreparedUpload,
    handleStart,
  } = form;

  return (
    <section className="space-y-4 bg-surface p-5 lg:sticky lg:top-4">
      <div>
        <p className="text-xs font-semibold text-primary">3. Launch the run</p>
        <h3 className="mt-1 text-base font-semibold text-text">Launch readiness</h3>
        <p className="mt-1 text-xs leading-relaxed text-text-muted">
          The run becomes available only when the document and every active criterion are ready.
        </p>
      </div>

      {/* Progress Tracker */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-text">Criteria Scored:</span>
          <span className="font-mono font-bold text-text tabular-nums">
            {enteredScoreCount} / {totalCriteriaCount} (
            {totalCriteriaCount > 0
              ? Math.round((enteredScoreCount / totalCriteriaCount) * 100)
              : 0}
            %)
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-surface-subtle overflow-hidden border border-border">
          <div
            className="h-full bg-primary transition-all duration-300 rounded-full"
            style={{
              width: `${totalCriteriaCount > 0 ? (enteredScoreCount / totalCriteriaCount) * 100 : 0}%`,
            }}
          />
        </div>
      </div>

      {/* Submission Controls */}
      {!uploaded ? (
        <div className="space-y-3 pt-2">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={
              !file ||
              !title.trim() ||
              !program ||
              !allCriterionScoresComplete ||
              uploadMutation.isPending
            }
            isLoading={uploadMutation.isPending}
            className="w-full h-10 text-xs sm:text-sm font-semibold"
          >
            <UploadSimple className="size-4" />
            <span>{uploadMutation.isPending ? 'Preparing SLM…' : 'Prepare validation'}</span>
          </Button>
          {!allCriterionScoresComplete && (
            <p className="text-[11px] text-text-muted leading-relaxed">
              Score all {totalCriteriaCount} criteria across agent tabs on the right to unlock
              submission.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {uploadedDocumentReady ? (
            <div className="flex items-center gap-2 text-xs font-semibold text-success">
              <CheckCircle className="size-4.5" />
              <span>SLM processed and ready</span>
            </div>
          ) : uploadedProcessingStatus === 'FAILED' ? (
            <div className="space-y-2 text-xs font-semibold text-destructive">
              <p>SLM processing failed. Upload the PDF again.</p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={resetPreparedUpload}
                className="text-xs h-7.5 px-3"
              >
                Choose another PDF
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs font-semibold text-text-muted">
              <Spinner className="size-4 animate-spin text-primary" />
              <span>Confirming SLM is processed…</span>
            </div>
          )}

          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={handleStart}
            disabled={!canSubmitEvaluation || validationMutation.isPending}
            isLoading={validationMutation.isPending}
            className="w-full h-10 text-xs sm:text-sm font-semibold gap-1.5"
          >
            <Play className="size-4" />
            <span>
              {validationMutation.isPending
                ? 'Starting…'
                : !uploadedDocumentReady
                  ? 'Waiting for SLM…'
                  : 'Start model validation'}
            </span>
          </Button>
        </div>
      )}

      {/* Stale Binding Alert */}
      {isStaleBinding && (
        <div
          role="alert"
          className="rounded-sm border border-destructive/40 bg-destructive-soft p-3.5 space-y-2 text-xs text-text"
        >
          <div className="flex items-start gap-2 text-destructive font-bold">
            <Warning className="size-4 shrink-0 mt-0.5" />
            <p>Active rubric criteria have changed</p>
          </div>
          <p className="text-[11px] text-text-muted leading-relaxed">
            The published rubric revisions or criteria were updated or retired while preparing this
            validation run.
          </p>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleReloadCatalog}
            disabled={criterionCatalog.isFetching}
            className="h-8 px-3 text-xs font-semibold gap-1.5"
          >
            <ArrowsClockwise
              className={criterionCatalog.isFetching ? 'size-3.5 animate-spin' : 'size-3.5'}
            />
            <span>Reload criteria catalog</span>
          </Button>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
        >
          {getErrorMessage(error, 'Unable to start model validation.')}
        </p>
      )}
    </section>
  );
}
