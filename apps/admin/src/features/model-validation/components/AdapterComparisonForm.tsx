import { CheckCircle, Play, Spinner, UploadSimple, Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import { ProgramSelector } from '@equiped/ui';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@equiped/types';
import { cn } from '@equiped/ui';
import type { AdapterComparisonFormState } from '../hooks/useAdapterComparisonFormState';
import { agentLabel, criterionKey } from '../utils/helpers';

export function AdapterComparisonForm({ form }: { form: AdapterComparisonFormState }) {
  const {
    fileInputRef,
    file,
    title,
    setTitle,
    program,
    handleProgramChange,
    selectedAgent,
    setSelectedAgent,
    expectedScores,
    setExpectedScores,
    uploaded,
    criterionCatalog,
    compareAgents,
    selectedAgentCriteria,
    uploadMutation,
    compareMutation,
    allCriterionScoresComplete,
    uploadedDocumentReady,
    canSubmitEvaluation,
    error,
    handleFile,
    handlePrepare,
    handleStart,
  } = form;

  return (
    <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border bg-surface-subtle px-6 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-sm border border-primary/20 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
              Synthetic Self-Test
            </span>
          </div>
          <h2 className="mt-1 text-sm sm:text-base font-bold text-text uppercase tracking-tight">
            Compare base vs adapter
          </h2>
          <p className="text-xs text-text-muted mt-0.5 max-w-2xl">
            Runs the same SLM twice — once with the plain model, once with the loaded LoRA adapter
            — and shows both results. Synthetic self-test data only; not a measure of real-world
            quality.
          </p>
        </div>
      </div>

      <form onSubmit={handlePrepare} className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-5 space-y-6">
            <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
              <div className="border-b border-border pb-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Step 1 of 2
                </span>
                <h3 className="text-sm font-bold text-text tracking-tight">SLM Document</h3>
              </div>
              <div className="space-y-3.5">
                <div className="space-y-1.5">
                  <label htmlFor="compare-title" className="text-xs font-semibold text-text">
                    SLM title <span className="text-destructive">*</span>
                  </label>
                  <input
                    id="compare-title"
                    className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text placeholder:text-text-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="e.g. Self-Test Pattern SLM"
                    required
                    disabled={!!uploaded}
                  />
                </div>
                <ProgramSelector
                  id="compare-program"
                  label="Confirmed program"
                  value={program}
                  onChange={handleProgramChange}
                  groups={LSPU_SCC_COLLEGE_PROGRAMS}
                  placeholder="Select the SLM program (BSCS or BSInfoTech)"
                  required
                  hint="Recorded as the confirmed program for this run."
                />
                <div className="pt-1">
                  <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-4 py-4 text-center hover:bg-surface-subtle hover:border-border-strong transition-colors focus-within:ring-2 focus-within:ring-ring">
                    <UploadSimple className="size-5 text-primary" aria-hidden="true" />
                    <span className="text-xs font-semibold text-text truncate max-w-full">
                      {file ? file.name : 'Choose an SLM PDF document'}
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

            <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
              <div className="border-b border-border pb-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Step 2 of 2
                </span>
                <h3 className="text-sm font-bold text-text tracking-tight">Run comparison</h3>
              </div>

              {!uploaded ? (
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={!file || !title.trim() || !program || uploadMutation.isPending}
                  isLoading={uploadMutation.isPending}
                  className="w-full h-10 text-xs sm:text-sm font-semibold"
                >
                  <UploadSimple className="size-4" />
                  <span>{uploadMutation.isPending ? 'Preparing SLM…' : 'Prepare comparison'}</span>
                </Button>
              ) : (
                <div className="space-y-4">
                  {uploadedDocumentReady ? (
                    <div className="flex items-center gap-2 text-xs font-semibold text-success">
                      <CheckCircle className="size-4.5" />
                      <span>SLM processed and ready</span>
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
                    disabled={!canSubmitEvaluation || compareMutation.isPending}
                    isLoading={compareMutation.isPending}
                    className="w-full h-10 text-xs sm:text-sm font-semibold gap-1.5"
                  >
                    <Play className="size-4" />
                    <span>
                      {compareMutation.isPending
                        ? 'Starting…'
                        : !canSubmitEvaluation
                          ? 'Waiting for SLM…'
                          : 'Start comparison'}
                    </span>
                  </Button>
                </div>
              )}

              {error && (
                <p
                  role="alert"
                  className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
                >
                  {getErrorMessage(error, 'Unable to start the comparison.')}
                </p>
              )}
            </div>
          </div>

          <div className="lg:col-span-7 space-y-5">
            <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
              <div className="border-b border-border bg-surface-subtle px-5 py-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                  Target agent
                </h3>
                <p className="text-[11px] text-text-muted mt-0.5">
                  Only this agent runs, twice — once with the adapter off, once on.
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5 p-2.5 border-b border-border bg-surface-subtle/50">
                {compareAgents.map((agent) => (
                  <button
                    key={agent.agent_id}
                    type="button"
                    onClick={() => setSelectedAgent(agent.agent_id as 'sme' | 'gad' | 'itso')}
                    className={cn(
                      'flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-sm transition-colors cursor-pointer border select-none',
                      selectedAgent === agent.agent_id
                        ? 'border-primary bg-primary text-primary-foreground font-bold shadow-2xs'
                        : 'border-border bg-surface text-text hover:bg-surface-subtle',
                    )}
                  >
                    {agentLabel(agent.agent_id)}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {criterionCatalog.isLoading ? (
                  <p className="text-xs text-text-muted">Loading criteria…</p>
                ) : !selectedAgent ? (
                  <p className="rounded-sm border border-border bg-surface-subtle p-4 text-xs font-semibold text-text-muted">
                    Choose a target agent above to enter its expected scores.
                  </p>
                ) : selectedAgentCriteria.length === 0 ? (
                  <p className="rounded-sm border border-warning/40 bg-warning-soft p-4 text-xs font-semibold text-text">
                    No active rubric criteria for this agent.
                  </p>
                ) : (
                  <div className="rounded-sm border border-border divide-y divide-border">
                    {selectedAgentCriteria.map((criterion) => {
                      const key = criterionKey(
                        selectedAgent,
                        criterion.rubric_criterion_id || criterion.criterion_id!,
                      );
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
                              {criterion.description}
                            </span>
                          </span>
                          <div className="flex items-center justify-end gap-1.5">
                            <input
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
                                setExpectedScores((current) => ({ ...current, [key]: nextScore }));
                              }}
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
                {selectedAgent && !allCriterionScoresComplete ? (
                  <p className="mt-3 flex items-start gap-1.5 text-[11px] text-text-muted">
                    <Warning className="size-3.5 shrink-0 mt-0.5" aria-hidden="true" />
                    Score every criterion above to enable the comparison.
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
