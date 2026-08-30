import {
  ArrowsClockwise,
  CaretDown,
  CheckCircle,
  Play,
  ShieldWarning,
  Spinner,
  UploadSimple,
  Warning,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import type { useModelValidationFormState } from '../hooks/useModelValidationFormState';
import { criterionKey } from '../utils/helpers';

type FormState = ReturnType<typeof useModelValidationFormState>;

export function ValidationPreparationForm({ form }: { form: FormState }) {
  const {
    fileInputRef,
    scoreInputRefs,
    file,
    title,
    setTitle,
    program,
    expectedScores,
    setExpectedScores,
    uploaded,
    partialChoiceAcknowledged,
    setPartialChoiceAcknowledged,
    criterionCatalog,
    uploadMutation,
    validationMutation,
    criterionDefinitions,
    allCriterionScoresComplete,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    canSubmitEvaluation,
    error,
    isStaleBinding,
    handleReloadCatalog,
    resetPreparedUpload,
    handleFile,
    handleProgramChange,
    handlePrepare,
    handleScoreKeyDown,
    handleStart,
  } = form;

  return (
    <details className="group overflow-hidden rounded-sm border border-border bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-3 bg-surface-subtle px-5 py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block text-sm font-bold uppercase tracking-wider text-text">
            New validation input
          </span>
          <span className="mt-1 block text-xs font-medium normal-case tracking-normal text-text-muted">
            Upload an SLM and enter the human benchmark for each active agent criterion.
          </span>
        </span>
        <span className="ml-auto hidden text-xs font-bold uppercase tracking-wider text-primary sm:block">
          Expand
        </span>
        <CaretDown
          className="size-5 shrink-0 text-primary transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <form onSubmit={handlePrepare} className="grid min-w-0 gap-5 border-t border-border p-5">
        <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-text-muted">
          SLM title
          <input
            className="h-10 min-w-0 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold normal-case tracking-normal text-text focus:outline-none focus:ring-2 focus:ring-ring"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            disabled={!!uploaded}
          />
        </label>

        <ProgramSelector
          id="validation-program"
          label="Confirmed program"
          value={program}
          onChange={handleProgramChange}
          groups={LSPU_SCC_COLLEGE_PROGRAMS}
          placeholder="Select the SLM program"
          required
          hint="Recorded as the confirmed program for this validation."
        />

        <div className="grid min-w-0 gap-4 border-t border-border pt-5">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-text">
              Expected criterion scores
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-text-muted">
              Enter the authoritative human score for every criterion before running the model.
            </p>
          </div>
          {criterionCatalog.isLoading ? (
            <p className="text-sm font-semibold text-text-muted">Loading active criteria…</p>
          ) : criterionCatalog.isError ? (
            <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-sm font-semibold text-destructive">
              <p>Unable to load the active rubric criteria.</p>
              <button
                type="button"
                onClick={() => criterionCatalog.refetch()}
                className="mt-2 text-xs font-bold uppercase tracking-wider underline hover:text-destructive/80"
              >
                Retry loading criteria
              </button>
            </div>
          ) : criterionDefinitions.length === 0 ||
            criterionDefinitions.some((agent) => {
              const count = agent.domains?.length
                ? agent.domains.reduce((sum, d) => sum + d.criteria.length, 0)
                : agent.criteria.length;
              return count === 0;
            }) ? (
            <p className="rounded-sm border border-warning/40 bg-warning-soft p-3 text-sm font-semibold text-text">
              No active rubric criteria are available for SME, GAD, or ITSO. Activate the evaluator
              agent rubrics first.
            </p>
          ) : (
            criterionDefinitions.map((agent) => {
              const hasDomains = agent.domains && agent.domains.length > 0;
              return (
                <section
                  key={agent.agent_id}
                  className="overflow-hidden rounded-sm border border-border bg-surface"
                >
                  <div className="flex min-w-0 items-center justify-between gap-3 border-b border-border bg-surface-subtle px-4 py-3">
                    <h3 className="min-w-0 break-words text-sm font-bold text-text">
                      {agent.agent_name}
                    </h3>
                    <span className="shrink-0 text-xs font-semibold text-text-muted tabular-nums">
                      Rubric v{agent.rubric_version}
                    </span>
                  </div>

                  {hasDomains ? (
                    <div className="divide-y divide-border">
                      {agent.domains.map((domain) => (
                        <div key={domain.rubric_domain_id} className="min-w-0">
                          <div className="flex items-center justify-between gap-2 bg-surface-subtle/70 px-4 py-2 text-xs font-bold uppercase tracking-wider text-text">
                            <span>
                              {domain.code} · {domain.title}
                            </span>
                            <span className="text-[10px] font-semibold text-text-muted normal-case tabular-nums">
                              Domain #{domain.display_order}
                            </span>
                          </div>
                          <div className="divide-y divide-border">
                            {domain.criteria.map((criterion) => {
                              const key = criterionKey(
                                agent.agent_id,
                                criterion.rubric_criterion_id,
                              );
                              return (
                                <label
                                  key={key}
                                  className="grid min-w-0 gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center"
                                >
                                  <span className="min-w-0">
                                    <span className="block break-words text-sm font-semibold text-text">
                                      {criterion.criterion_code} · {criterion.title}
                                    </span>
                                    <span className="mt-0.5 block break-words text-xs leading-relaxed text-text-muted">
                                      {criterion.domain_title ?? domain.title} —{' '}
                                      {criterion.description}
                                    </span>
                                  </span>
                                  <span className="grid min-w-0 gap-1 text-xs font-bold uppercase tracking-wider text-text-muted">
                                    Score
                                    <input
                                      ref={(node) => {
                                        scoreInputRefs.current[key] = node;
                                      }}
                                      type="text"
                                      inputMode="numeric"
                                      pattern="[1-4]"
                                      maxLength={1}
                                      autoComplete="off"
                                      placeholder="1–4"
                                      value={expectedScores[key] ?? ''}
                                      onChange={(event) => {
                                        const nextScore = event.target.value;
                                        if (!/^[1-4]?$/.test(nextScore)) return;
                                        setExpectedScores((current) => ({
                                          ...current,
                                          [key]: nextScore,
                                        }));
                                      }}
                                      onWheel={(event) => {
                                        event.currentTarget.blur();
                                      }}
                                      onKeyDown={(event) => handleScoreKeyDown(event, key)}
                                      onFocus={(event) => event.currentTarget.select()}
                                      className="h-10 min-w-0 w-full rounded-sm border border-input bg-surface px-3 text-sm font-bold text-text tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                                      required
                                      aria-label={`Expected score for ${criterion.criterion_code} ${criterion.title}`}
                                    />
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="divide-y divide-border">
                      {agent.criteria.map((criterion) => {
                        const key = criterionKey(
                          agent.agent_id,
                          criterion.rubric_criterion_id || criterion.criterion_id!,
                        );
                        return (
                          <label
                            key={key}
                            className="grid min-w-0 gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center"
                          >
                            <span className="min-w-0">
                              <span className="block break-words text-sm font-semibold text-text">
                                {criterion.criterion_code} · {criterion.title}
                              </span>
                              <span className="mt-0.5 block break-words text-xs leading-relaxed text-text-muted">
                                {criterion.domain_title} — {criterion.description}
                              </span>
                            </span>
                            <span className="grid min-w-0 gap-1 text-xs font-bold uppercase tracking-wider text-text-muted">
                              <input
                                ref={(node) => {
                                  scoreInputRefs.current[key] = node;
                                }}
                                type="text"
                                inputMode="numeric"
                                pattern="[1-4]"
                                maxLength={1}
                                autoComplete="off"
                                placeholder="1–4"
                                value={expectedScores[key] ?? ''}
                                onChange={(event) => {
                                  const nextScore = event.target.value;
                                  if (!/^[1-4]?$/.test(nextScore)) return;
                                  setExpectedScores((current) => ({
                                    ...current,
                                    [key]: nextScore,
                                  }));
                                }}
                                onWheel={(event) => {
                                  event.currentTarget.blur();
                                }}
                                onKeyDown={(event) => handleScoreKeyDown(event, key)}
                                onFocus={(event) => event.currentTarget.select()}
                                className="h-10 min-w-0 w-full rounded-sm border border-input bg-surface px-3 text-sm font-bold text-text tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
                                required
                                aria-label={`Expected score for ${criterion.criterion_code} ${criterion.title}`}
                              />
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })
          )}
        </div>

        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-4 py-6 text-center focus-within:ring-2 focus-within:ring-ring">
          <UploadSimple className="size-6 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold text-text">
            {file?.name ?? 'Choose an SLM PDF'}
          </span>
          <span className="text-xs font-medium text-text-muted">
            The file is stored locally and evaluated as direct input.
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="sr-only"
            onChange={handleFile}
            disabled={!!uploaded}
            required={!uploaded}
          />
        </label>

        {!uploaded ? (
          <button
            type="submit"
            disabled={
              !file ||
              !title.trim() ||
              !program ||
              !allCriterionScoresComplete ||
              uploadMutation.isPending
            }
            className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-primary px-4 text-sm font-semibold uppercase tracking-wide text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {uploadMutation.isPending ? (
              <Spinner className="size-4 animate-spin" />
            ) : (
              <UploadSimple className="size-4" />
            )}
            {uploadMutation.isPending ? 'Preparing SLM…' : 'Prepare validation'}
          </button>
        ) : (
          <div className="grid gap-4 border-t border-border pt-5">
            {uploadedDocumentReady ? (
              <div className="flex items-center gap-2 text-sm font-semibold text-success">
                <CheckCircle className="size-5" />
                SLM processed and ready
              </div>
            ) : uploadedProcessingStatus === 'FAILED' ? (
              <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-destructive">
                <span>SLM processing failed. Upload the PDF again before validation.</span>
                <button
                  type="button"
                  onClick={resetPreparedUpload}
                  className="rounded-sm border border-destructive/40 bg-surface px-3 py-2 text-xs font-bold uppercase tracking-wider text-destructive hover:bg-destructive-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
                >
                  Choose another PDF
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm font-semibold text-text-muted">
                <Spinner className="size-5 animate-spin text-primary" />
                Confirming the SLM is fully processed…
              </div>
            )}

            {uploadedDocumentReady ? (
              <fieldset className="grid gap-3 rounded-sm border border-warning/40 bg-warning-soft p-4 text-sm text-text">
                <legend className="px-1 text-xs font-bold uppercase tracking-wider text-text">
                  Partial validation
                </legend>
                <p className="flex items-start gap-2 leading-relaxed font-semibold text-text">
                  <ShieldWarning
                    className="mt-0.5 size-4 shrink-0 text-destructive"
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    This validation runs without a curriculum reference. The Coordinator agent will
                    be skipped; SME, GAD, and ITSO will still evaluate the SLM. The result is marked
                    partial and remains advisory.
                  </span>
                </p>
                <label className="flex items-start gap-3 border-t border-warning/30 pt-3 text-xs font-semibold text-text">
                  <input
                    type="checkbox"
                    checked={partialChoiceAcknowledged}
                    onChange={(event) => setPartialChoiceAcknowledged(event.target.checked)}
                    className="mt-0.5 size-4 shrink-0 accent-primary"
                    aria-describedby="validation-partial-acknowledgement-help"
                  />
                  <span
                    id="validation-partial-acknowledgement-help"
                    className="min-w-0 leading-relaxed"
                  >
                    I understand that the Coordinator agent will be skipped and the validation will
                    be reported as a partial result.
                  </span>
                </label>
              </fieldset>
            ) : null}

            <button
              type="button"
              onClick={handleStart}
              disabled={!canSubmitEvaluation || validationMutation.isPending}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-primary px-4 text-sm font-semibold uppercase tracking-wide text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {validationMutation.isPending || !uploadedDocumentReady ? (
                <Spinner className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              {validationMutation.isPending
                ? 'Starting…'
                : !uploadedDocumentReady
                  ? 'Waiting for SLM…'
                  : 'Start model validation'}
            </button>
          </div>
        )}

        {isStaleBinding ? (
          <div
            role="alert"
            className="rounded-sm border border-destructive/40 bg-destructive-soft p-4 text-text"
          >
            <div className="flex items-start gap-3">
              <Warning className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
              <div className="min-w-0 flex-1 space-y-2">
                <p className="text-sm font-bold text-destructive">
                  Active rubric criteria have changed
                </p>
                <p className="text-xs leading-relaxed text-text">
                  The published rubric revisions or criteria were updated or retired while preparing
                  this validation run. Benchmark scores must match currently active revisions.
                  Please reload the criteria catalog to update the form before resubmitting.
                </p>
                {validationMutation.error ? (
                  <p className="rounded-xs border border-border bg-surface/70 px-2 py-1 font-mono text-[11px] text-text-muted">
                    {getErrorMessage(validationMutation.error)}
                  </p>
                ) : null}
                <div>
                  <button
                    type="button"
                    onClick={handleReloadCatalog}
                    disabled={criterionCatalog.isFetching}
                    className="inline-flex items-center gap-2 rounded-sm bg-destructive px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-destructive-foreground hover:bg-destructive/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50"
                  >
                    <ArrowsClockwise
                      className={criterionCatalog.isFetching ? 'size-3.5 animate-spin' : 'size-3.5'}
                    />
                    {criterionCatalog.isFetching ? 'Reloading catalog…' : 'Reload criteria catalog'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : error ? (
          <p
            role="alert"
            className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-sm font-semibold text-destructive"
          >
            {getErrorMessage(error, 'Unable to start model validation.')}
          </p>
        ) : null}
      </form>
    </details>
  );
}
