import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  WarningCircle,
  BookOpen,
  Spinner,
  Play,
  ShieldWarning,
  CheckCircle,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import { documentsApi } from '@/shared/api/documents.api';
import {
  canStartEvaluation,
  type EvaluationMode,
} from '@/features/evaluation/utils/setupState';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
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
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between border-b border-border/60 py-2 first:pt-0 last:border-b-0 last:pb-0 text-xs">
      <dt className="font-semibold text-text-muted">{label}:</dt>
      <dd className="font-bold text-text truncate max-w-[18rem]">{value}</dd>
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

  // Derive effective selection purely from raw selection + ready list
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
    <section className="min-h-0 flex-1 overflow-y-auto bg-canvas">
      <div className="mx-auto max-w-3xl space-y-6 px-4 sm:px-6 py-8">
        {/* Header Bar */}
        <div className="border-b border-border pb-4 space-y-1">
          <p className={TYPOGRAPHY.labelMuted}>
            New Evaluation Pipeline
          </p>
          <h1 className={TYPOGRAPHY.headingLg}>Evaluation Setup</h1>
          <p className="text-xs text-text-muted leading-relaxed max-w-2xl">
            Confirm the owning academic program and choose between a full 4-domain curriculum evaluation or an advisory partial review. Nothing is submitted until you click Start Evaluation below.
          </p>
        </div>

        {/* Loading SLM Metadata */}
        {isLoadingDocument ? (
          <div
            role="status"
            className="flex items-center gap-3 rounded-sm border border-border bg-surface p-4 text-xs font-semibold text-text-muted"
          >
            <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
            <span>Loading SLM metadata…</span>
          </div>
        ) : null}

        {/* Document Error */}
        {documentError ? (
          <div
            role="alert"
            className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive"
          >
            {getErrorMessage(documentError, 'Unable to load the selected document.')}
          </div>
        ) : null}

        {/* Resolve Error */}
        {isResolveError ? (
          <div
            role="alert"
            className="rounded-sm border border-destructive/30 bg-destructive-soft p-5 text-sm text-destructive"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <WarningCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
                <div className="flex-1">
                  <p className="font-bold text-text">Unable to verify existing evaluations</p>
                  <p className="mt-1 text-xs leading-relaxed text-destructive">
                    {getErrorMessage(
                      resolveError,
                      'Could not check for existing evaluations on this document. You must resolve this check before configuring a new evaluation.',
                    )}
                  </p>
                </div>
              </div>
              {onRetryResolve ? (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={onRetryResolve}
                >
                  Retry Check
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Section 1: Detected from SLM */}
        {canConfigure && document ? (
          <div className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-3 shadow-none">
            <div className="flex items-center gap-2">
              <BookOpen className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-text">
                Detected from SLM
              </h2>
            </div>
            <dl className="border border-border rounded-sm p-3.5 bg-surface-subtle">
              <MetadataRow label="Course Code" value={document.courseCode} />
              <MetadataRow label="Sem/AY" value={document.academicYear} />
              <MetadataRow label="Lesson" value={document.lessonTitle} />
              {document.program ? (
                <MetadataRow label="Program" value={document.program.trim()} />
              ) : null}
            </dl>
            {document.program && !detectedProgram ? (
              <p className="rounded-sm border border-warning/30 bg-warning-soft px-3 py-2 text-xs font-semibold text-warning">
                The detected program is not an official LSPU SCC program code. Select the owning program from the list below.
              </p>
            ) : null}
          </div>
        ) : null}

        {/* Section 2: Academic Program Confirmation */}
        {canConfigure ? (
          <div className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
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
            <label className="flex items-start gap-3 border-t border-border pt-4 text-xs font-semibold text-text cursor-pointer select-none">
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
                className="mt-0.5 size-4 shrink-0 accent-primary rounded-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
          <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
            <legend className="text-xs font-bold uppercase tracking-wider text-text px-1">
              Select Evaluation Mode
            </legend>
            <p className="text-xs text-text-muted leading-relaxed">
              Choose whether to run a full 4-domain review against an institutional curriculum reference or an advisory partial review without coordinator alignment.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              {/* Full Mode Card */}
              <label
                htmlFor="mode-full"
                className={cn(
                  'relative flex flex-col justify-between gap-3 p-4 rounded-sm border transition-all cursor-pointer select-none',
                  evaluationMode === 'full'
                    ? 'border-primary bg-primary-soft/50 ring-1 ring-primary'
                    : 'border-border bg-surface hover:bg-surface-subtle',
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
                    className="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-text">Full Evaluation</span>
                      <Badge variant="success">4 Domains</Badge>
                    </div>
                    <p className="text-xs text-text-muted mt-1.5 leading-relaxed">
                      Evaluates SME, Program Coordinator (Curriculum Alignment), GAD, and ITSO. Requires an active curriculum reference.
                    </p>
                  </div>
                </div>
              </label>

              {/* Partial Mode Card */}
              <label
                htmlFor="mode-partial"
                className={cn(
                  'relative flex flex-col justify-between gap-3 p-4 rounded-sm border transition-all cursor-pointer select-none',
                  evaluationMode === 'partial'
                    ? 'border-primary bg-primary-soft/50 ring-1 ring-primary'
                    : 'border-border bg-surface hover:bg-surface-subtle',
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
                    className="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-text">Partial Evaluation</span>
                      <Badge variant="warning">3 Domains</Badge>
                    </div>
                    <p className="text-xs text-text-muted mt-1.5 leading-relaxed">
                      Evaluates SME, GAD, and ITSO domains only. The Program Coordinator review is skipped and the result is marked as partial.
                    </p>
                  </div>
                </div>
              </label>
            </div>
          </fieldset>
        ) : null}

        {/* Section 4A: Full Evaluation Curriculum Selection */}
        {canConfigure && evaluationMode === 'full' ? (
          <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
            <legend className="text-xs font-bold uppercase tracking-wider text-text px-1">
              Select Curriculum Reference
            </legend>
            <p className="text-xs text-text-muted leading-relaxed">
              Select an active institutional curriculum to evaluate module learning outcomes and topic sequence alignment. Faculty must select a curriculum reference to start.
            </p>

            {isLoadingCurricula ? (
              <div
                role="status"
                className="flex items-center gap-3 rounded-sm border border-border bg-surface p-4 text-xs font-semibold text-text-muted"
              >
                <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
                <span>Loading curriculum references for {selectedProgram}…</span>
              </div>
            ) : null}

            {isCurriculaError ? (
              <div
                role="alert"
                className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs text-destructive"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-bold">Unable to load curriculum suggestions</p>
                    <p className="text-xs mt-1">
                      {getErrorMessage(curriculaError, 'Failed to fetch curriculum options.')}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={() => refetchCurricula()}
                  >
                    Retry
                  </Button>
                </div>
              </div>
            ) : null}

            {!isLoadingCurricula && !isCurriculaError && readyCurricula.length > 0 ? (
              <div className="space-y-2">
                {readyCurricula.map((curriculum) => {
                  const isSelected = effectiveSelectedCurriculumId === curriculum.documentId;
                  return (
                    <label
                      key={curriculum.documentId}
                      htmlFor={`curriculum-${curriculum.documentId}`}
                      className={cn(
                        'flex items-start gap-3 p-3.5 rounded-sm border transition-all cursor-pointer select-none',
                        isSelected
                          ? 'border-primary bg-primary-soft/50 ring-1 ring-primary'
                          : 'border-border bg-surface hover:bg-surface-subtle',
                      )}
                    >
                      <input
                        type="radio"
                        id={`curriculum-${curriculum.documentId}`}
                        name="curriculum-selection"
                        value={curriculum.documentId}
                        checked={isSelected}
                        onChange={() => setSelectedCurriculumId(curriculum.documentId)}
                        className="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-text truncate">
                            {curriculum.title}
                          </span>
                          <Badge variant="success">Ready</Badge>
                        </div>
                        <p className="text-xs text-text-muted mt-0.5">
                          Program: {curriculum.program || selectedProgram}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            ) : null}

            {!isLoadingCurricula && !isCurriculaError && readyCurricula.length === 0 ? (
              <div className="rounded-sm border border-warning/30 bg-warning-soft p-4 text-xs text-warning leading-relaxed">
                <strong>No ready curricula available: </strong>
                <span>There are no published curriculum maps for {selectedProgram}. You can switch to Partial Evaluation above or upload a curriculum reference in the Admin Workspace.</span>
              </div>
            ) : null}

            {unavailableCurricula.length > 0 ? (
              <div className="space-y-2 pt-3 border-t border-border">
                <p className="text-[11px] font-bold text-text-muted uppercase tracking-wider">
                  Unavailable references ({unavailableCurricula.length})
                </p>
                {unavailableCurricula.map((curriculum) => (
                  <label
                    key={curriculum.documentId}
                    htmlFor={`curriculum-unavailable-${curriculum.documentId}`}
                    className="flex items-start gap-3 p-3 rounded-sm border border-border bg-surface-subtle/50 opacity-60 cursor-not-allowed select-none"
                  >
                    <input
                      type="radio"
                      id={`curriculum-unavailable-${curriculum.documentId}`}
                      name="curriculum-selection"
                      disabled
                      aria-label={`Unavailable curriculum: ${curriculum.title}`}
                      className="mt-1 size-4 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-semibold text-text truncate block">
                        {curriculum.title}
                      </span>
                      <p className="text-[11px] text-text-muted">
                        {curriculum.matchReason || 'Not ready for evaluation'}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            ) : null}
          </fieldset>
        ) : null}
        {/* Section 4B: Partial Evaluation Acknowledgement */}
        {canConfigure && evaluationMode === 'partial' ? (
          <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
            <legend className="text-xs font-bold uppercase tracking-wider text-text px-1">
              Partial Evaluation Acknowledgement
            </legend>
            <div className="rounded-sm border border-warning/30 bg-warning-soft p-4 space-y-2 text-xs text-warning">
              <div className="flex items-center gap-2">
                <ShieldWarning className="size-4 shrink-0 text-warning" aria-hidden="true" />
                <span className="font-bold">Coordinator Review Exclusion Notice</span>
              </div>
              <p className="leading-relaxed">
                You have chosen to evaluate this SLM without an institutional curriculum reference. The Program Coordinator domain (Curriculum Map Alignment) will be excluded, and the resulting scorecard will be permanently marked as Partial.
              </p>
            </div>

            <label className="flex items-start gap-3 text-xs font-semibold text-text cursor-pointer select-none pt-1">
              <input
                type="checkbox"
                id="partial-acknowledge-checkbox"
                checked={partialAcknowledged}
                onChange={(e) => setPartialAcknowledged(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 accent-primary rounded-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="min-w-0 leading-relaxed">
                I understand that the Program Coordinator review will be skipped and acknowledge this partial evaluation.
              </span>
            </label>
          </fieldset>
        ) : null}
        {/* Submit Action Bar */}
        {canConfigure ? (
          <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-none">
            <div>
              <h3 className="text-sm font-bold text-text">Ready to Start</h3>
              <p className="text-xs text-text-muted mt-0.5">
                {canStart
                  ? 'All prerequisites verified. Click start to admit the job into the queue.'
                  : !programConfirmed
                    ? 'Confirm the academic program above to continue.'
                    : !evaluationMode
                      ? 'Select Full or Partial evaluation mode.'
                      : evaluationMode === 'full' && !effectiveSelectedCurriculumId
                        ? 'Select a ready curriculum reference.'
                        : 'Acknowledge the partial evaluation notice to proceed.'}
              </p>
            </div>

            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={handleStart}
              disabled={!canStart || isSubmitting}
              className="shrink-0 font-bold uppercase tracking-wider text-xs h-10 px-5"
            >
              {isSubmitting ? (
                <span className="inline-flex items-center gap-2">
                  <Spinner className="size-4 animate-spin" aria-hidden="true" />
                  Starting…
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Play className="size-3.5" aria-hidden="true" weight="fill" />
                  <span>Start Evaluation</span>
                </span>
              )}
            </Button>
          </div>
        ) : null}

        {submitError ? (
          <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive flex items-center justify-between gap-3" role="alert">
            <span>{getErrorMessage(submitError, 'Failed to submit evaluation.')}</span>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={onRetrySubmit}
            >
              Retry
            </Button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
