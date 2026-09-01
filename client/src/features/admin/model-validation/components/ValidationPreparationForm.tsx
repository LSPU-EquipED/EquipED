import { useState } from 'react';
import {
  ArrowsClockwise,
  CheckCircle,
  Play,
  ShieldWarning,
  Spinner,
  UploadSimple,
  Warning,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/Button';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import { cn } from '@/shared/components/utils';
import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';
import { criterionKey } from '../utils/helpers';

export function ValidationPreparationForm({ form }: { form: ModelValidationFormState }) {
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

  const [activeAgentTab, setActiveAgentTab] = useState<string>('sme');

  // Calculate entered scores count
  const enteredScoreCount = Object.values(expectedScores).filter(
    (val) => val && /^[1-4]$/.test(val),
  ).length;

  const totalCriteriaCount = criterionDefinitions.reduce((acc, agent) => {
    const agentCount = agent.domains?.length
      ? agent.domains.reduce((sum, d) => sum + d.criteria.length, 0)
      : agent.criteria?.length ?? 0;
    return acc + agentCount;
  }, 0);

  return (
    <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
      {/* ── Workbench Header & Context Strip ───────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border bg-surface-subtle px-6 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-sm border border-primary/20 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
              Benchmark Input
            </span>
            <span className="text-xs text-text-muted">·</span>
            <span className="text-xs text-text-muted font-medium">Authoritative 1–4 Scoring Ground Truth</span>
          </div>
          <h2 className="mt-1 text-sm sm:text-base font-bold text-text uppercase tracking-tight">
            New validation input
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Upload an SLM and enter the human benchmark for each active agent criterion.
          </p>
        </div>

        {totalCriteriaCount > 0 ? (
          <div className="flex items-center gap-2 font-mono text-xs tabular-nums text-text shrink-0 bg-surface border border-border rounded-sm px-3 py-1.5">
            <span className="text-text-muted font-sans font-medium text-[11px]">Progress:</span>
            <strong className="font-bold text-primary">{enteredScoreCount}</strong>
            <span className="text-text-muted">/</span>
            <span>{totalCriteriaCount} criteria scored</span>
          </div>
        ) : null}
      </div>

      <form onSubmit={handlePrepare} className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* ── Left Column (5 cols): SLM Document & Submission Pipeline ── */}
          <div className="lg:col-span-5 space-y-6">
            {/* Card 1: Document Metadata & File */}
            <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
              <div className="border-b border-border pb-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Step 1 of 2
                </span>
                <h3 className="text-sm font-bold text-text tracking-tight">
                  SLM Document Identification
                </h3>
              </div>

              <div className="space-y-3.5">
                <div className="space-y-1.5">
                  <label htmlFor="validation-title" className="text-xs font-semibold text-text">
                    SLM title <span className="text-destructive">*</span>
                  </label>
                  <input
                    id="validation-title"
                    className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text placeholder:text-text-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="e.g. CS101 Algorithms Benchmark SLM"
                    required
                    disabled={!!uploaded}
                  />
                </div>

                <ProgramSelector
                  id="validation-program"
                  label="Confirmed program"
                  value={program}
                  onChange={handleProgramChange}
                  groups={LSPU_SCC_COLLEGE_PROGRAMS}
                  placeholder="Select the SLM program (BSCS or BSInfoTech)"
                  required
                  hint="Recorded as the confirmed program for this validation."
                />

                {/* PDF Dropzone */}
                <div className="pt-1">
                  <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-4 py-4 text-center hover:bg-surface-subtle hover:border-border-strong transition-colors focus-within:ring-2 focus-within:ring-ring">
                    <UploadSimple className="size-5 text-primary" aria-hidden="true" />
                    <span className="text-xs font-semibold text-text truncate max-w-full">
                      {file ? file.name : 'Choose an SLM PDF document'}
                    </span>
                    <span className="text-[10px] text-text-muted">
                      Direct evaluation input; never embedded.
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
                </div>
              </div>
            </div>

            {/* Card 2: Benchmark Readiness & Execution */}
            <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
              <div className="border-b border-border pb-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Step 2 of 2
                </span>
                <h3 className="text-sm font-bold text-text tracking-tight">
                  Benchmark Submission
                </h3>
              </div>

              {/* Progress Tracker */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-text">Criteria Scored:</span>
                  <span className="font-mono font-bold text-text tabular-nums">
                    {enteredScoreCount} / {totalCriteriaCount} ({totalCriteriaCount > 0 ? Math.round((enteredScoreCount / totalCriteriaCount) * 100) : 0}%)
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
                      Score all {totalCriteriaCount} criteria across agent tabs on the right to unlock submission.
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

                  {uploadedDocumentReady ? (
                    <fieldset className="grid gap-2.5 rounded-sm border border-warning/40 bg-warning-soft p-3.5 text-xs text-text">
                      <legend className="px-1 text-[11px] font-bold uppercase tracking-wider text-text">
                        Partial validation
                      </legend>
                      <p className="flex items-start gap-1.5 leading-relaxed font-semibold text-text">
                        <ShieldWarning className="size-4 shrink-0 text-destructive mt-0.5" />
                        <span>
                          Runs without curriculum reference; Coordinator will be skipped.
                        </span>
                      </p>
                      <label className="flex items-start gap-2.5 border-t border-warning/30 pt-2 text-[11px] font-semibold text-text cursor-pointer">
                        <input
                          type="checkbox"
                          checked={partialChoiceAcknowledged}
                          onChange={(event) => setPartialChoiceAcknowledged(event.target.checked)}
                          className="mt-0.5 size-3.5 shrink-0 accent-primary"
                          aria-describedby="validation-partial-acknowledgement-help"
                        />
                        <span id="validation-partial-acknowledgement-help" className="leading-relaxed">
                          I understand that the Coordinator agent will be skipped and the validation will be reported as a partial result.
                        </span>
                      </label>
                    </fieldset>
                  ) : null}

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
                <div role="alert" className="rounded-sm border border-destructive/40 bg-destructive-soft p-3.5 space-y-2 text-xs text-text">
                  <div className="flex items-start gap-2 text-destructive font-bold">
                    <Warning className="size-4 shrink-0 mt-0.5" />
                    <p>Active rubric criteria have changed</p>
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">
                    The published rubric revisions or criteria were updated or retired while preparing this validation run.
                  </p>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={handleReloadCatalog}
                    disabled={criterionCatalog.isFetching}
                    className="h-8 px-3 text-xs font-semibold gap-1.5"
                  >
                    <ArrowsClockwise className={criterionCatalog.isFetching ? 'size-3.5 animate-spin' : 'size-3.5'} />
                    <span>Reload criteria catalog</span>
                  </Button>
                </div>
              )}

              {error && (
                <p role="alert" className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive">
                  {getErrorMessage(error, 'Unable to start model validation.')}
                </p>
              )}
            </div>
          </div>

          {/* ── Right Column (7 cols): Specialist Agent Benchmark Scoring ── */}
          <div className="lg:col-span-7 space-y-5">
            {/* Header & Sub-Tabs Bar */}
            <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
              <div className="border-b border-border bg-surface-subtle px-5 py-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                  Expected criterion scores
                </h3>
                <p className="text-[11px] text-text-muted mt-0.5">
                  Select an evaluator agent to grade criteria on the authoritative 1–4 scale.
                </p>
              </div>

              {/* Agent Sub-Tabs */}
              <div className="flex flex-wrap gap-1.5 p-2.5 border-b border-border bg-surface-subtle/50">
                {criterionDefinitions.map((agent) => {
                  const isTabActive = (activeAgentTab || criterionDefinitions[0]?.agent_id) === agent.agent_id;
                  const criteriaList = agent.domains?.length
                    ? agent.domains.flatMap((d) => d.criteria)
                    : agent.criteria ?? [];
                  const agentScoreCount = criteriaList.filter((c) => {
                    const k = criterionKey(agent.agent_id, c.rubric_criterion_id || c.criterion_id!);
                    return expectedScores[k] && /^[1-4]$/.test(expectedScores[k]);
                  }).length;
                  const isComplete = criteriaList.length > 0 && agentScoreCount === criteriaList.length;

                  return (
                    <button
                      key={agent.agent_id}
                      type="button"
                      onClick={() => setActiveAgentTab(agent.agent_id)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-sm transition-colors cursor-pointer border select-none',
                        isTabActive
                          ? 'border-primary bg-primary text-primary-foreground font-bold shadow-2xs'
                          : 'border-border bg-surface text-text hover:bg-surface-subtle',
                      )}
                    >
                      <span>{agent.agent_name}</span>
                      <span
                        className={cn(
                          'rounded-xs px-1.5 py-0.2 text-[10px] font-mono tabular-nums font-bold border',
                          isTabActive
                            ? 'bg-primary-foreground/20 text-primary-foreground border-transparent'
                            : isComplete
                              ? 'bg-success-soft text-success border-success/30'
                              : 'bg-surface-subtle text-text-muted border-border',
                        )}
                      >
                        {agentScoreCount}/{criteriaList.length}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Criteria Panels per Agent */}
              <div className="p-5">
                {criterionCatalog.isLoading ? (
                  <p className="text-sm font-semibold text-text-muted py-8 text-center">Loading active criteria…</p>
                ) : criterionCatalog.isError ? (
                  <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-sm font-semibold text-destructive">
                    <p>Unable to load the active rubric criteria.</p>
                    <button
                      type="button"
                      onClick={() => criterionCatalog.refetch()}
                      className="mt-2 text-xs font-bold uppercase tracking-wider underline hover:text-destructive/80 cursor-pointer"
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
                  <p className="rounded-sm border border-warning/40 bg-warning-soft p-4 text-sm font-semibold text-text">
                    No active rubric criteria are available for SME, GAD, or ITSO. Activate the evaluator
                    agent rubrics first.
                  </p>
                ) : (
                  criterionDefinitions.map((agent) => {
                    const isVisible = (activeAgentTab || criterionDefinitions[0]?.agent_id) === agent.agent_id;
                    const hasDomains = agent.domains && agent.domains.length > 0;

                    return (
                      <div
                        key={agent.agent_id}
                        className={cn(isVisible ? 'space-y-4' : 'hidden')}
                      >
                        <div className="flex items-center justify-between pb-2 border-b border-border">
                          <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                            Active Criteria
                          </span>
                          <span className="rounded-xs border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-mono font-semibold text-text-muted tabular-nums">
                            Rubric v{agent.rubric_version}
                          </span>
                        </div>

                        {hasDomains ? (
                          <div className="space-y-3.5">
                            {agent.domains.map((domain) => (
                              <div key={domain.rubric_domain_id} className="rounded-sm border border-border overflow-hidden">
                                <div className="flex items-center justify-between bg-surface-subtle px-4 py-2 border-b border-border">
                                  <span className="text-xs font-semibold text-text">
                                    {domain.code} · {domain.title}
                                  </span>
                                  <span className="text-[10px] font-mono text-text-muted tabular-nums">
                                    Domain #{domain.display_order}
                                  </span>
                                </div>
                                <div className="divide-y divide-border">
                                  {domain.criteria.map((criterion) => {
                                    const key = criterionKey(agent.agent_id, criterion.rubric_criterion_id);
                                    const val = expectedScores[key] ?? '';
                                    return (
                                      <label
                                        key={key}
                                        className="grid grid-cols-[minmax(0,1fr)_6.5rem] items-center gap-3 p-3.5 hover:bg-surface-subtle/40 transition-colors cursor-pointer"
                                      >
                                        <span className="min-w-0">
                                          <span className="block text-xs font-semibold text-text">
                                            {criterion.criterion_code} · {criterion.title}
                                          </span>
                                          <span className="mt-0.5 block text-[11px] text-text-muted leading-relaxed">
                                            {criterion.domain_title ?? domain.title} — {criterion.description}
                                          </span>
                                        </span>
                                        <div className="flex items-center justify-end gap-1.5">
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
                                            value={val}
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
                                            className={cn(
                                              'h-9 w-16 rounded-sm border bg-surface px-2.5 text-sm font-bold tabular-nums text-center transition-colors',
                                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                              val
                                                ? 'border-primary text-primary bg-primary-soft/30'
                                                : 'border-input text-text',
                                            )}
                                            required
                                            aria-label={`Expected score for ${criterion.criterion_code} ${criterion.title}`}
                                          />
                                        </div>
                                      </label>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded-sm border border-border divide-y divide-border">
                            {agent.criteria.map((criterion) => {
                              const key = criterionKey(agent.agent_id, criterion.rubric_criterion_id || criterion.criterion_id!);
                              const val = expectedScores[key] ?? '';
                              return (
                                <label
                                  key={key}
                                  className="grid grid-cols-[minmax(0,1fr)_6.5rem] items-center gap-3 p-3.5 hover:bg-surface-subtle/40 transition-colors cursor-pointer"
                                >
                                  <span className="min-w-0">
                                    <span className="block text-xs font-semibold text-text">
                                      {criterion.criterion_code} · {criterion.title}
                                    </span>
                                    <span className="mt-0.5 block text-[11px] text-text-muted leading-relaxed">
                                      {criterion.domain_title} — {criterion.description}
                                    </span>
                                  </span>
                                  <div className="flex items-center justify-end gap-1.5">
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
                                      value={val}
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
                                      className={cn(
                                        'h-9 w-16 rounded-sm border bg-surface px-2.5 text-sm font-bold tabular-nums text-center transition-colors',
                                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                        val
                                          ? 'border-primary text-primary bg-primary-soft/30'
                                          : 'border-input text-text',
                                      )}
                                      required
                                      aria-label={`Expected score for ${criterion.criterion_code} ${criterion.title}`}
                                    />
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
