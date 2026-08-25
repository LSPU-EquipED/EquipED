import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  BookOpen,
  Loader2,
  Play,
  ShieldAlert,
} from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import { documentsApi } from '@/shared/api/documents.api';
import {
  canStartEvaluation,
  type EvaluationMode,
} from '@/features/evaluation/utils/setupState';
import { cn } from '@/shared/components/utils';
import type { ClientDocument, CurriculumSuggestionItem } from '@/shared/types/documents';

export type EvaluationSetupProps = {
  document: ClientDocument | null | undefined;
  isLoadingDocument: boolean;
  documentError: unknown;
  selectedProgram: string;
  detectedProgram: string | null;
  onSelectProgram: (program: string) => void;
  isResolveError: boolean;
  resolveError: unknown;
  onRetryResolve?: () => void;
  isSubmitting: boolean;
  submitError: unknown;
  onSubmit: (params: {
    program: string;
    mode: EvaluationMode;
    curriculumId?: string | null;
  }) => void;
  onRetrySubmit: () => void;
};

const EMPTY_CURRICULA: CurriculumSuggestionItem[] = [];

function MetadataRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] items-baseline gap-3 py-1.5">
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="text-sm font-semibold text-slate-900">
        {value ?? <span className="font-medium text-slate-400">Not detected</span>}
      </dd>
    </div>
  );
}

export function EvaluationSetup({
  document,
  isLoadingDocument,
  documentError,
  selectedProgram,
  detectedProgram,
  onSelectProgram,
  isResolveError,
  resolveError,
  onRetryResolve,
  isSubmitting,
  submitError,
  onSubmit,
  onRetrySubmit,
}: EvaluationSetupProps) {
  const [programConfirmed, setProgramConfirmed] = useState(false);
  const [evaluationMode, setEvaluationMode] = useState<EvaluationMode | null>(null);
  const [selectedCurriculumId, setSelectedCurriculumId] = useState<string | null>(null);
  const [partialAcknowledged, setPartialAcknowledged] = useState(false);

  // When the user changes the program in the dropdown, reset all downstream state
  const handleProgramChange = (newProgram: string) => {
    onSelectProgram(newProgram);
    setProgramConfirmed(false);
    setEvaluationMode(null);
    setSelectedCurriculumId(null);
    setPartialAcknowledged(false);
  };

  // Curriculum suggestions query keyed by document ID + selected program
  // Gated so it runs only after explicit program confirmation and when full mode is selected
  const {
    data: curriculumData,
    isLoading: isLoadingCurricula,
    isError: isCurriculaError,
    error: curriculaError,
    refetch: refetchCurricula,
  } = useQuery({
    queryKey: ['curriculum-suggestion', document?.documentId, selectedProgram],
    queryFn: () => documentsApi.getCurriculumSuggestion(document!.documentId, selectedProgram),
    enabled: Boolean(
      document?.documentId &&
        selectedProgram &&
        !isResolveError &&
        programConfirmed &&
        evaluationMode === 'full',
    ),
    staleTime: 30000,
  });

  const readyCurricula = curriculumData?.curriculumSuggestions ?? EMPTY_CURRICULA;
  const unavailableCurricula = curriculumData?.unavailableCurricula ?? EMPTY_CURRICULA;

  // Derive effective selection purely from raw selection + ready list (no synchronous setState effect)
  const effectiveSelectedCurriculumId =
    selectedCurriculumId && readyCurricula.some((c) => c.documentId === selectedCurriculumId)
      ? selectedCurriculumId
      : null;

  const canConfigure = !isLoadingDocument && !documentError && !isResolveError && Boolean(document);

  const canStart = canStartEvaluation({
    program: selectedProgram,
    programConfirmed,
    mode: evaluationMode,
    selectedCurriculumId: effectiveSelectedCurriculumId,
    readyCurriculumIds: readyCurricula.map((c) => c.documentId),
    partialAcknowledged,
    isLoadingCurricula: evaluationMode === 'full' && isLoadingCurricula,
    isCurriculaError: evaluationMode === 'full' && isCurriculaError,
    isResolveError,
    isSubmitting,
  });

  const handleStart = () => {
    if (!canStart || !evaluationMode) return;
    onSubmit({
      program: selectedProgram,
      mode: evaluationMode,
      curriculumId: evaluationMode === 'full' ? effectiveSelectedCurriculumId : undefined,
    });
  };

  return (
    <section className="min-h-0 flex-1 overflow-y-auto bg-white">
      <div className="mx-auto grid max-w-2xl gap-8 px-6 py-10">
        {/* Header */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            New Evaluation
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Evaluation Setup</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Configure your evaluation by confirming the academic program and choosing between a full
            4-domain review with curriculum alignment or an advisory partial review. Nothing is
            submitted until you choose to start.
          </p>
        </div>

        {/* Loading SLM Metadata */}
        {isLoadingDocument ? (
          <div
            role="status"
            className="flex items-center gap-3 rounded-sm border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
            <span>Loading SLM metadata…</span>
          </div>
        ) : null}

        {/* Document Error */}
        {documentError ? (
          <div
            role="alert"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]"
          >
            {getErrorMessage(documentError, 'Unable to load the selected document.')}
          </div>
        ) : null}

        {/* Resolve Error - Blocks all fresh submission and provides retry-only state */}
        {isResolveError ? (
          <div
            role="alert"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-5 py-4 text-sm text-[#b91c1c]"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-[#b91c1c]" aria-hidden="true" />
                <div className="flex-1">
                  <p className="font-bold text-slate-900">Unable to verify existing evaluations</p>
                  <p className="mt-1 text-xs leading-relaxed text-[#b91c1c]">
                    {getErrorMessage(
                      resolveError,
                      'Could not check for existing evaluations on this document. You must resolve this check before configuring a new evaluation.',
                    )}
                  </p>
                </div>
              </div>
              {onRetryResolve ? (
                <button
                  type="button"
                  onClick={onRetryResolve}
                  className="rounded-sm bg-[#b91c1c] px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#b91c1c]/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b91c1c] shrink-0 min-h-[32px]"
                >
                  Retry Check
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Section 1: Detected from SLM (rendered only when no blocking error) */}
        {canConfigure && document ? (
          <div className="rounded-sm border border-slate-200 bg-white p-5">
            <div className="mb-4 flex items-center gap-2">
              <BookOpen className="size-4 text-[#1b3b87]" aria-hidden="true" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                Detected from SLM
              </h2>
            </div>
            <dl>
              <MetadataRow label="Course Code" value={document.courseCode} />
              <MetadataRow label="Sem/AY" value={document.academicYear} />
              <MetadataRow label="Lesson" value={document.lessonTitle} />
              {document.program ? (
                <MetadataRow label="Program" value={document.program.trim()} />
              ) : null}
            </dl>
            {document.program && !detectedProgram ? (
              <p className="mt-3 rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 px-3 py-2 text-xs font-semibold text-[#1e293b]">
                The detected program is not an official LSPU SCC program code. Select the owning
                program from the list below.
              </p>
            ) : null}
          </div>
        ) : null}

        {/* Section 2: Academic Program Confirmation */}
        {canConfigure ? (
          <div className="rounded-sm border border-slate-200 bg-white p-5">
            <ProgramSelector
              id="program-select"
              label="Academic Program"
              value={selectedProgram}
              onChange={handleProgramChange}
              groups={LSPU_SCC_COLLEGE_PROGRAMS}
              placeholder="Select a program"
              hint={
                detectedProgram
                  ? 'The detected program is preselected as a suggestion. Change it if it is not correct, then confirm below.'
                  : 'No program was detected in the SLM. Select the owning program, then confirm below.'
              }
            />
            <label className="mt-4 flex items-start gap-3 border-t border-slate-100 pt-4 text-sm font-semibold text-slate-900 cursor-pointer min-h-[24px]">
              <input
                type="checkbox"
                id="program-confirm-checkbox"
                checked={programConfirmed}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setProgramConfirmed(checked);
                  if (!checked) {
                    setEvaluationMode(null);
                    setSelectedCurriculumId(null);
                    setPartialAcknowledged(false);
                  }
                }}
                className="mt-1 size-4 shrink-0 accent-[#1b3b87] rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                aria-describedby="program-confirm-help"
              />
              <span id="program-confirm-help" className="min-w-0 leading-relaxed">
                I confirm this SLM belongs to the selected program.
              </span>
            </label>
          </div>
        ) : null}

        {/* Section 3: Evaluation Mode (Full vs Partial) */}
        {canConfigure ? (
          <fieldset className="rounded-sm border border-slate-200 bg-white p-5 space-y-4">
            <legend className="text-sm font-bold uppercase tracking-wider text-slate-900 px-1">
              Select Evaluation Mode
            </legend>
            <p className="text-xs text-slate-500 leading-relaxed">
              Choose whether to run a full 4-agent evaluation against a curriculum reference or an
              advisory partial review without coordinator alignment.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              {/* Mode Option 1: Full Evaluation */}
              <label
                htmlFor="mode-full"
                className={cn(
                  'relative flex flex-col justify-between gap-3 p-4 rounded-sm border transition-colors cursor-pointer min-h-[120px]',
                  evaluationMode === 'full'
                    ? 'border-[#1b3b87] bg-[#1b3b87]/5 ring-1 ring-[#1b3b87]'
                    : 'border-slate-200 hover:bg-slate-50/80',
                  !programConfirmed && 'opacity-60 cursor-not-allowed',
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    id="mode-full"
                    name="evaluation-mode"
                    value="full"
                    disabled={!programConfirmed}
                    checked={evaluationMode === 'full'}
                    onChange={() => {
                      setEvaluationMode('full');
                      setSelectedCurriculumId(null);
                      setPartialAcknowledged(false);
                    }}
                    className="mt-1 size-4 shrink-0 accent-[#1b3b87] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-slate-900">Full Evaluation</span>
                      <span className="inline-flex rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30">
                        4 Domains
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                      Evaluates SME, Program Coordinator (Curriculum Alignment), GAD, and ITSO. Requires
                      an active curriculum reference.
                    </p>
                  </div>
                </div>
              </label>

              {/* Mode Option 2: Partial Evaluation */}
              <label
                htmlFor="mode-partial"
                className={cn(
                  'relative flex flex-col justify-between gap-3 p-4 rounded-sm border transition-colors cursor-pointer min-h-[120px]',
                  evaluationMode === 'partial'
                    ? 'border-[#1b3b87] bg-[#1b3b87]/5 ring-1 ring-[#1b3b87]'
                    : 'border-slate-200 hover:bg-slate-50/80',
                  !programConfirmed && 'opacity-60 cursor-not-allowed',
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    id="mode-partial"
                    name="evaluation-mode"
                    value="partial"
                    disabled={!programConfirmed}
                    checked={evaluationMode === 'partial'}
                    onChange={() => {
                      setEvaluationMode('partial');
                      setSelectedCurriculumId(null);
                      setPartialAcknowledged(false);
                    }}
                    className="mt-1 size-4 shrink-0 accent-[#1b3b87] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-slate-900">Partial Evaluation</span>
                      <span className="inline-flex rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-[#f2c811]/20 text-[#854d0e] border border-[#f2c811]/40">
                        3 Domains
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                      Evaluates SME, GAD, and ITSO domains only. The Program Coordinator review is
                      skipped and the result is marked as partial.
                    </p>
                  </div>
                </div>
              </label>
            </div>
          </fieldset>
        ) : null}

        {/* Section 4A: Full Evaluation Details (Curriculum Selection) */}
        {canConfigure && evaluationMode === 'full' ? (
          <fieldset className="rounded-sm border border-slate-200 bg-white p-5 space-y-4">
            <legend className="text-sm font-bold uppercase tracking-wider text-slate-900 px-1">
              Select Curriculum Reference
            </legend>
            <p className="text-xs text-slate-500 leading-relaxed">
              Select an active institutional curriculum to evaluate module learning outcomes and topic
              sequence alignment. Faculty must select a curriculum reference to start.
            </p>

            {/* Curriculum Loading State */}
            {isLoadingCurricula ? (
              <div
                role="status"
                className="flex items-center gap-3 rounded-sm border border-slate-200 bg-slate-50 p-4 text-xs font-semibold uppercase tracking-wider text-slate-600"
              >
                <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
                <span>Loading curriculum references for {selectedProgram}…</span>
              </div>
            ) : null}

            {/* Curriculum Error State */}
            {isCurriculaError ? (
              <div
                role="alert"
                className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-4 text-sm text-[#b91c1c]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">Unable to load curriculum suggestions</p>
                    <p className="text-xs mt-1 text-[#b91c1c]/90">
                      {getErrorMessage(curriculaError, 'Failed to fetch curriculum options.')}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => refetchCurricula()}
                    className="rounded-sm bg-[#b91c1c] px-3 py-1 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#b91c1c]/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b91c1c]"
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : null}

            {/* Ready Curricula List */}
            {!isLoadingCurricula && !isCurriculaError && readyCurricula.length > 0 ? (
              <div className="space-y-2.5">
                {readyCurricula.map((curriculum) => {
                  const isSelected = effectiveSelectedCurriculumId === curriculum.documentId;
                  return (
                    <label
                      key={curriculum.documentId}
                      htmlFor={`curriculum-${curriculum.documentId}`}
                      className={cn(
                        'flex items-start gap-3 p-3.5 rounded-sm border transition-colors cursor-pointer min-h-[48px]',
                        isSelected
                          ? 'border-[#1b3b87] bg-[#1b3b87]/5 ring-1 ring-[#1b3b87]'
                          : 'border-slate-200 hover:bg-slate-50/80',
                      )}
                    >
                      <input
                        type="radio"
                        id={`curriculum-${curriculum.documentId}`}
                        name="curriculum-selection"
                        value={curriculum.documentId}
                        checked={isSelected}
                        onChange={() => setSelectedCurriculumId(curriculum.documentId)}
                        className="mt-1 size-4 shrink-0 accent-[#1b3b87] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-slate-900 truncate">
                            {curriculum.title}
                          </span>
                          <span className="inline-flex rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30 shrink-0">
                            Ready
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Program: {curriculum.program || selectedProgram}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            ) : null}

            {/* Empty Ready Curricula */}
            {!isLoadingCurricula && !isCurriculaError && readyCurricula.length === 0 ? (
              <div className="rounded-sm border border-[#f2c811]/40 bg-[#f2c811]/10 p-4 text-xs text-[#1e293b]">
                <p className="font-semibold text-slate-900">No ready curriculum reference available</p>
                <p className="mt-1 leading-relaxed text-slate-600">
                  No vectorized curriculum was found for {selectedProgram}. An administrator must upload
                  and vectorize a curriculum before a Full evaluation can run. You can switch to Partial
                  Evaluation above.
                </p>
              </div>
            ) : null}

            {/* Unavailable Admin Curricula List - Fully accessible with explicit name & label */}
            {!isLoadingCurricula && unavailableCurricula.length > 0 ? (
              <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Unavailable Curricula (Pending Vectorization by Admin)
                </p>
                {unavailableCurricula.map((curriculum) => {
                  const inputId = `unavailable-curriculum-${curriculum.documentId}`;
                  return (
                    <div
                      key={curriculum.documentId}
                      className="flex items-start gap-3 p-3 rounded-sm border border-slate-200 bg-slate-50/60 opacity-60 cursor-not-allowed min-h-[48px]"
                    >
                      <input
                        type="radio"
                        id={inputId}
                        disabled
                        aria-disabled="true"
                        aria-label={`Unavailable curriculum: ${curriculum.title}`}
                        className="mt-1 size-4 shrink-0 cursor-not-allowed text-slate-300"
                      />
                      <label htmlFor={inputId} className="flex-1 min-w-0 cursor-not-allowed">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-700 truncate">
                            {curriculum.title}
                          </span>
                          <span className="inline-flex rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-slate-200 text-slate-600 shrink-0">
                            Unavailable
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Pending embedding/indexing by admin
                        </p>
                      </label>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </fieldset>
        ) : null}

        {/* Section 4B: Partial Evaluation Details & Conditional Acknowledgement */}
        {canConfigure && evaluationMode === 'partial' ? (
          <div className="rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-5 space-y-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 size-5 shrink-0 text-[#854d0e]" aria-hidden="true" />
              <div className="flex-1">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                  Partial Review Terms
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-[#1e293b]">
                  This evaluation runs without a curriculum reference. The Program Coordinator
                  review will be skipped; SME, GAD, and ITSO will still review the SLM. The result
                  is reported as partial and remains advisory.
                </p>
              </div>
            </div>

            <label
              htmlFor="partial-ack-checkbox"
              className="flex items-start gap-3 border-t border-[#f2c811]/40 pt-4 text-sm font-semibold text-slate-900 cursor-pointer min-h-[24px]"
            >
              <input
                type="checkbox"
                id="partial-ack-checkbox"
                checked={partialAcknowledged}
                onChange={(event) => setPartialAcknowledged(event.target.checked)}
                className="mt-1 size-4 shrink-0 accent-[#1b3b87] rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                aria-describedby="partial-acknowledgement-help"
              />
              <span id="partial-acknowledgement-help" className="min-w-0 leading-relaxed">
                I understand that the Program Coordinator review will be skipped and the result will
                be marked as a partial evaluation.
              </span>
            </label>
          </div>
        ) : null}

        {/* Section 5: Submission Controls */}
        {canConfigure ? (
          <div className="space-y-4">
            {submitError ? (
              <div
                role="alert"
                className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="flex-1">
                    <p>{getErrorMessage(submitError, 'Failed to start evaluation.')}</p>
                    <button
                      type="button"
                      onClick={onRetrySubmit}
                      className="mt-2 inline-flex h-8 items-center justify-center border border-[#b91c1c]/30 px-3 text-xs font-bold uppercase tracking-wide text-[#b91c1c] transition-colors hover:bg-[#b91c1c]/10 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b91c1c]"
                    >
                      Retry
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            <button
              type="button"
              onClick={handleStart}
              disabled={!canStart}
              className="inline-flex h-11 w-full items-center justify-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px]"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  <span>Starting evaluation…</span>
                </>
              ) : (
                <>
                  <Play className="size-4" aria-hidden="true" />
                  <span>Start Evaluation</span>
                </>
              )}
            </button>

            {!canStart && !isSubmitting ? (
              <p className="text-center text-xs font-medium text-slate-500 leading-relaxed">
                {!selectedProgram
                  ? 'Select and confirm an academic program to continue.'
                  : !programConfirmed
                    ? 'Confirm the academic program to continue.'
                    : !evaluationMode
                      ? 'Select an evaluation mode to continue.'
                      : evaluationMode === 'full' && !effectiveSelectedCurriculumId
                        ? 'Select a curriculum reference to start full evaluation.'
                        : evaluationMode === 'partial' && !partialAcknowledged
                          ? 'Acknowledge the partial review terms to start partial evaluation.'
                          : 'Complete the required setup steps to start.'}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
