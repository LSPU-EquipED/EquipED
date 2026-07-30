import {
  CheckCircle,
  ChevronDown,
  FileCheck2,
  Loader2,
  Play,
  ShieldAlert,
  Upload,
} from 'lucide-react';
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
    curriculumId,
    setCurriculumId,
    allowPartial,
    setAllowPartial,
    partialChoiceAcknowledged,
    setPartialChoiceAcknowledged,
    criterionCatalog,
    uploadMutation,
    validationMutation,
    criterionDefinitions,
    allCriterionScoresComplete,
    readyCurricula,
    unavailableCurricula,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    isSuggestionsLoading,
    isSuggestionsError,
    showPartialOption,
    canSubmitEvaluation,
    error,
    normalizedProgram,
    resetPreparedUpload,
    handleFile,
    handleProgramChange,
    handlePrepare,
    handleScoreKeyDown,
    handleStart,
  } = form;

  return (
    <details className="group overflow-hidden rounded-sm border border-slate-200 bg-white">
      <summary className="flex cursor-pointer list-none items-center gap-3 bg-slate-50 px-5 py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1b3b87] [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block text-sm font-bold uppercase tracking-wider text-slate-800">
            New validation input
          </span>
          <span className="mt-1 block text-xs font-medium normal-case tracking-normal text-slate-600">
            Upload an SLM and enter the human benchmark for each active agent criterion.
          </span>
        </span>
        <span className="ml-auto hidden text-xs font-bold uppercase tracking-wider text-[#1b3b87] sm:block">
          Expand
        </span>
        <ChevronDown
          className="size-5 shrink-0 text-[#1b3b87] transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <form onSubmit={handlePrepare} className="grid min-w-0 gap-5 border-t border-slate-200 p-5">
        <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
          SLM title
          <input
            className="h-10 min-w-0 w-full rounded-sm border border-slate-200 px-3 text-sm font-semibold normal-case tracking-normal focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
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
          hint="Used to find the matching indexed curriculum."
        />

        <div className="grid min-w-0 gap-4 border-t border-slate-200 pt-5">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
              Expected criterion scores
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-600">
              Enter the authoritative human score for every criterion before running the model.
            </p>
          </div>
          {criterionCatalog.isLoading ? (
            <p className="text-sm font-semibold text-slate-600">Loading active criteria…</p>
          ) : criterionCatalog.isError ? (
            <p className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-3 text-sm font-semibold text-[#b91c1c]">
              Unable to load the active rubric criteria.
            </p>
          ) : criterionDefinitions.length !== 4 ||
            criterionDefinitions.some((agent) => agent.criteria.length === 0) ? (
            <p className="rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-3 text-sm font-semibold text-slate-800">
              No active rubric criteria are available. Activate all four agent rubrics first.
            </p>
          ) : (
            criterionDefinitions.map((agent) => (
              <section
                key={agent.agent_id}
                className="overflow-hidden rounded-sm border border-slate-200"
              >
                <div className="flex min-w-0 items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
                  <h3 className="min-w-0 break-words text-sm font-bold text-slate-900">
                    {agent.agent_name}
                  </h3>
                  <span className="shrink-0 text-xs font-semibold text-slate-600">
                    Rubric v{agent.rubric_version}
                  </span>
                </div>
                <div className="divide-y divide-slate-200">
                  {agent.criteria.map((criterion) => {
                    const key = criterionKey(agent.agent_id, criterion.criterion_id);
                    return (
                      <label
                        key={key}
                        className="grid min-w-0 gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center"
                      >
                        <span className="min-w-0">
                          <span className="block break-words text-sm font-semibold text-slate-900">
                            {criterion.criterion_id} · {criterion.title}
                          </span>
                          <span className="mt-0.5 block break-words text-xs leading-relaxed text-slate-600">
                            {criterion.domain_title} — {criterion.description}
                          </span>
                        </span>
                        <span className="grid min-w-0 gap-1 text-xs font-bold uppercase tracking-wider text-slate-600">
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
                            onKeyDown={(event) => handleScoreKeyDown(event, key)}
                            onFocus={(event) => event.currentTarget.select()}
                            className="h-10 min-w-0 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                            required
                          />
                        </span>
                      </label>
                    );
                  })}
                </div>
              </section>
            ))
          )}
        </div>

        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center focus-within:ring-2 focus-within:ring-[#1b3b87]">
          <Upload className="size-6 text-[#1b3b87]" aria-hidden="true" />
          <span className="text-sm font-semibold text-slate-800">
            {file?.name ?? 'Choose an SLM PDF'}
          </span>
          <span className="text-xs font-medium text-slate-600">
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
            className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
          >
            {uploadMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileCheck2 className="size-4" />
            )}
            {uploadMutation.isPending ? 'Preparing SLM…' : 'Prepare validation'}
          </button>
        ) : (
          <div className="grid gap-4 border-t border-slate-200 pt-5">
            {uploadedDocumentReady ? (
              <div className="flex items-center gap-2 text-sm font-semibold text-[#3b963e]">
                <CheckCircle className="size-5" />
                SLM processed and ready
              </div>
            ) : uploadedProcessingStatus === 'FAILED' ? (
              <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-[#b91c1c]">
                <span>SLM processing failed. Upload the PDF again before validation.</span>
                <button
                  type="button"
                  onClick={resetPreparedUpload}
                  className="rounded-sm border border-[#b91c1c]/40 bg-white px-3 py-2 text-xs font-bold uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-[#b91c1c]"
                >
                  Choose another PDF
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Loader2 className="size-5 animate-spin text-[#1b3b87]" />
                Confirming the SLM is fully processed…
              </div>
            )}
            {uploadedDocumentReady && isSuggestionsLoading ? (
              <div
                role="status"
                className="flex items-center gap-2 rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600"
              >
                <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
                Loading curriculum suggestions for {normalizedProgram}…
              </div>
            ) : null}
            {uploadedDocumentReady && isSuggestionsError ? (
              <p
                role="alert"
                className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-3 text-sm font-semibold text-[#b91c1c]"
              >
                Unable to load curriculum suggestions for {normalizedProgram}. Try a different
                program or retry the upload.
              </p>
            ) : null}
            {uploadedDocumentReady &&
            !isSuggestionsLoading &&
            !isSuggestionsError &&
            readyCurricula.length ? (
              <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                Curriculum reference
                <select
                  value={curriculumId}
                  onChange={(event) => setCurriculumId(event.target.value)}
                  className="h-10 min-w-0 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-semibold normal-case tracking-normal focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                >
                  {readyCurricula.map((item) => (
                    <option key={item.documentId} value={item.documentId}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {uploadedDocumentReady &&
            !isSuggestionsLoading &&
            !isSuggestionsError &&
            unavailableCurricula.length > 0 ? (
              <div className="rounded-sm border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
                <p className="font-semibold text-slate-800">
                  Unavailable curricula for {normalizedProgram}
                </p>
                <p className="mt-1">
                  {unavailableCurricula.length} reference
                  {unavailableCurricula.length === 1 ? '' : 's'} not ready for retrieval. Ask an
                  admin to rebuild or re-upload them before full evaluation.
                </p>
              </div>
            ) : null}
            {showPartialOption && !isSuggestionsLoading && !isSuggestionsError ? (
              <fieldset className="grid gap-3 rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-4 text-sm text-slate-900">
                <legend className="px-1 text-xs font-bold uppercase tracking-wider text-slate-800">
                  Partial validation opt-in
                </legend>
                <label className="flex items-start gap-3 font-semibold text-slate-900">
                  <input
                    type="checkbox"
                    checked={allowPartial}
                    onChange={(event) => {
                      setAllowPartial(event.target.checked);
                      if (!event.target.checked) {
                        setPartialChoiceAcknowledged(false);
                      }
                    }}
                    className="mt-1 size-4 shrink-0 accent-[#1b3b87]"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-slate-900">
                      Continue with a partial validation.
                    </span>
                    <span className="mt-1 block text-xs font-medium leading-relaxed text-slate-700">
                      No indexed curriculum is available for {normalizedProgram}. Coordinator
                      curriculum-grounded review will be skipped. SME, GAD, and ITSO will still
                      evaluate the SLM. The result is marked partial and remains advisory.
                    </span>
                  </span>
                </label>
                {allowPartial ? (
                  <label className="flex items-start gap-3 border-t border-[#f2c811]/40 pt-3 text-xs font-semibold text-slate-800">
                    <input
                      type="checkbox"
                      checked={partialChoiceAcknowledged}
                      onChange={(event) => setPartialChoiceAcknowledged(event.target.checked)}
                      className="mt-0.5 size-4 shrink-0 accent-[#1b3b87]"
                      aria-describedby="partial-acknowledgement-help"
                    />
                    <span id="partial-acknowledgement-help" className="min-w-0 leading-relaxed">
                      I understand that the Coordinator agent will be skipped and the evaluation
                      will be reported as a partial result.
                    </span>
                  </label>
                ) : null}
                <p
                  id="partial-mode-warning"
                  className="flex items-start gap-2 border-t border-[#f2c811]/40 pt-3 text-xs font-semibold text-slate-800"
                >
                  <ShieldAlert
                    className="mt-0.5 size-4 shrink-0 text-[#b91c1c]"
                    aria-hidden="true"
                  />
                  <span className="leading-relaxed">
                    Partial validation never claims curriculum-grounded Coordinator review
                    occurred. Pick a different program above to use a ready curriculum instead.
                  </span>
                </p>
              </fieldset>
            ) : null}
            <button
              type="button"
              onClick={handleStart}
              disabled={!canSubmitEvaluation || validationMutation.isPending}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            >
              {validationMutation.isPending || !uploadedDocumentReady ? (
                <Loader2 className="size-4 animate-spin" />
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

        {error ? (
          <p
            role="alert"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]"
          >
            {getErrorMessage(error, 'Unable to start model validation.')}
          </p>
        ) : null}
      </form>
    </details>
  );
}
