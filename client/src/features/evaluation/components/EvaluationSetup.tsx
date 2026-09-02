import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  Check,
  CheckCircle,
  Circle,
  FileText,
  GraduationCap,
  ListChecks,
  ListNumbers,
  Play,
  ShieldCheck,
  ShieldWarning,
  Spinner,
  WarningCircle,
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
import { Skeleton } from '@/shared/components/Skeleton';
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
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between py-1.5 text-xs">
      <dt className="text-text-muted">{label}</dt>
      <dd className="font-semibold text-text truncate max-w-[13rem] sm:max-w-[16rem] text-right">
        {value}
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

  // When the user changes the program in the dropdown, reset downstream state
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

  // Extract detected topic outline from chunks or structuredOutline
  const detectedTopics = useMemo(() => {
    if (!document) return [];

    if (
      document.structuredOutline &&
      Array.isArray(document.structuredOutline) &&
      document.structuredOutline.length > 0
    ) {
      return document.structuredOutline.map((item, idx) => {
        const title = typeof item.title === 'string' ? item.title : `Section ${idx + 1}`;
        return { index: idx + 1, title };
      });
    }

    const topics: string[] = [];
    if (document.chunks && document.chunks.length > 0) {
      for (const chunk of document.chunks) {
        const lines = chunk.text.split('\n').map((l) => l.trim()).filter(Boolean);
        if (lines.length > 0) {
          const firstLine = lines[0];
          if (firstLine.length < 80 && !topics.includes(firstLine)) {
            topics.push(firstLine);
          }
        }
        if (topics.length >= 5) break;
      }
    }

    if (topics.length > 0) {
      return topics.map((title, idx) => ({ index: idx + 1, title }));
    }

    return [
      { index: 1, title: 'Core Concepts & Pedagogical Flow' },
      { index: 2, title: 'Instructional Activities & Demonstrations' },
      { index: 3, title: 'Formative Assessment & Evaluation' },
    ];
  }, [document]);

  const pageCount = document?.pageCount ?? document?.chunks?.length ?? 1;

  // Loading document state
  if (isLoadingDocument) {
    return (
      <section className="flex flex-1 min-h-0 items-center justify-center p-8 bg-canvas">
        <div
          role="status"
          aria-label="Loading SLM metadata"
          className="w-full max-w-xl space-y-4 rounded-md border border-border bg-surface p-6 shadow-none"
        >
          <div className="flex items-center gap-3">
            <Skeleton className="size-8 rounded-xs" />
            <div className="space-y-1.5 flex-1">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
          <div className="space-y-2.5 pt-4 border-t border-border">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      </section>
    );
  }

  // Document loading error
  if (documentError) {
    return (
      <section className="flex flex-1 min-h-0 items-center justify-center p-8 bg-canvas">
        <div
          role="alert"
          className="w-full max-w-xl rounded-md border border-destructive/30 bg-destructive-soft p-6 text-xs font-semibold text-destructive space-y-3"
        >
          <div className="flex items-center gap-2">
            <WarningCircle className="size-5 text-destructive shrink-0" aria-hidden="true" />
            <span className="font-bold text-sm">Failed to Load Learning Material</span>
          </div>
          <p>{String(getErrorMessage(documentError, 'Unable to load the selected document.'))}</p>
        </div>
      </section>
    );
  }

  // Evaluation resolve error
  if (isResolveError) {
    return (
      <section className="flex flex-1 min-h-0 items-center justify-center p-8 bg-canvas">
        <div
          role="alert"
          className="w-full max-w-2xl rounded-md border border-destructive/30 bg-destructive-soft p-6 text-destructive space-y-4"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <WarningCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
              <div className="space-y-1">
                <p className="font-bold text-sm text-text">Unable to verify existing evaluations</p>
                <p className="text-xs leading-relaxed text-destructive">
                  {String(
                    getErrorMessage(
                      resolveError,
                      'Could not check for existing evaluations on this document. You must resolve this check before configuring a new evaluation.',
                    ),
                  )}
                </p>
              </div>
            </div>
            {onRetryResolve && (
              <Button type="button" variant="destructive" size="sm" onClick={onRetryResolve}>
                Retry Check
              </Button>
            )}
          </div>
        </div>
      </section>
    );
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[24rem_minmax(0,1fr)] xl:grid-cols-[27rem_minmax(0,1fr)] bg-canvas">
      {/* ── LEFT PANE: Structured SLM Dossier ────────────────────────────── */}
      <aside
        aria-label="SLM Intake Dossier"
        className="flex flex-col h-full min-h-0 border-r border-border bg-canvas/60 overflow-y-auto p-5 sm:p-6 space-y-4"
      >
        {/* Card 1: Metadata Ledger */}
        <div className="rounded-md border border-border bg-surface p-4.5 space-y-3 shadow-none">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-primary shrink-0" aria-hidden="true" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-text">
                Detected from SLM
              </h2>
            </div>
            <span className="text-[11px] font-mono text-text-muted tabular-nums">
              {pageCount} {pageCount === 1 ? 'Page' : 'Pages'}
            </span>
          </div>

          <dl className="rounded-sm bg-surface-subtle/80 px-3 py-2 space-y-0.5">
            <MetadataRow label="Course Code" value={document?.courseCode} />
            <MetadataRow label="Sem/AY" value={document?.academicYear} />
            <MetadataRow label="Lesson" value={document?.lessonTitle} />
            {document?.program && (
              <MetadataRow label="Program" value={document.program.trim()} />
            )}
            <MetadataRow
              label="Format"
              value={document?.hasOcrPages ? 'OCR Scanned Document' : 'Digital Native PDF'}
            />
          </dl>

          {document?.program && !detectedProgram && (
            <p className="rounded-xs border border-warning/30 bg-warning-soft px-3 py-2 text-xs font-semibold text-warning leading-relaxed">
              The detected program is not an official LSPU SCC program code. Select the owning program on the right.
            </p>
          )}
        </div>

        {/* Card 2: Extracted Structure Outline */}
        {detectedTopics.length > 0 && (
          <div className="rounded-md border border-border bg-surface p-4.5 space-y-3 shadow-none">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ListNumbers className="size-4 text-primary shrink-0" aria-hidden="true" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                  Extracted Structure
                </h3>
              </div>
              <span className="text-[11px] font-mono font-semibold text-text-muted tabular-nums">
                {detectedTopics.length} Units
              </span>
            </div>

            <ol className="space-y-1.5 text-xs">
              {detectedTopics.map((topic) => (
                <li key={topic.index} className="flex items-start gap-2.5 text-text py-0.5">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-xs bg-surface-subtle border border-border text-[10px] font-mono font-bold text-text-muted mt-0.5">
                    {topic.index}
                  </span>
                  <span className="truncate leading-relaxed font-medium" title={topic.title}>
                    {topic.title}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Card 3: Pre-Flight Readiness Checklist */}
        <div className="rounded-md border border-border bg-surface p-4.5 space-y-3 shadow-none">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ListChecks className="size-4 text-primary shrink-0" aria-hidden="true" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                Pre-Flight Checklist
              </h3>
            </div>
            <span className="text-[10px] font-mono font-bold uppercase text-primary">
              {canStart ? '4/4 Ready' : 'Prerequisites'}
            </span>
          </div>

          <ul className="space-y-2 text-xs">
            <li className="flex items-center justify-between gap-2 py-0.5">
              <div className="flex items-center gap-2">
                <CheckCircle className="size-3.5 text-success shrink-0" weight="fill" />
                <span className="text-text font-medium">Document Parsed</span>
              </div>
              <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-xs bg-success-soft text-success border border-success/20">
                READY
              </span>
            </li>

            <li className="flex items-center justify-between gap-2 py-0.5">
              <div className="flex items-center gap-2">
                {programConfirmed ? (
                  <CheckCircle className="size-3.5 text-success shrink-0" weight="fill" />
                ) : (
                  <Circle className="size-3.5 text-text-muted/60 shrink-0" />
                )}
                <span className="text-text font-medium">Program Binding</span>
              </div>
              <span
                className={cn(
                  'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-xs border',
                  programConfirmed
                    ? 'bg-success-soft text-success border-success/20'
                    : 'bg-surface-subtle text-text-muted border-border',
                )}
              >
                {programConfirmed ? 'CONFIRMED' : 'PENDING'}
              </span>
            </li>

            <li className="flex items-center justify-between gap-2 py-0.5">
              <div className="flex items-center gap-2">
                {evaluationMode ? (
                  <CheckCircle className="size-3.5 text-success shrink-0" weight="fill" />
                ) : (
                  <Circle className="size-3.5 text-text-muted/60 shrink-0" />
                )}
                <span className="text-text font-medium">Review Protocol</span>
              </div>
              <span
                className={cn(
                  'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-xs border',
                  evaluationMode
                    ? 'bg-primary-soft text-primary border-primary/20'
                    : 'bg-surface-subtle text-text-muted border-border',
                )}
              >
                {evaluationMode === 'full'
                  ? 'FULL (4 DOM)'
                  : evaluationMode === 'partial'
                    ? 'PARTIAL (3 DOM)'
                    : 'REQUIRED'}
              </span>
            </li>

            <li className="flex items-center justify-between gap-2 py-0.5">
              <div className="flex items-center gap-2">
                {effectiveSelectedCurriculumId || partialAcknowledged ? (
                  <CheckCircle className="size-3.5 text-success shrink-0" weight="fill" />
                ) : (
                  <Circle className="size-3.5 text-text-muted/60 shrink-0" />
                )}
                <span className="text-text font-medium">Reference Anchor</span>
              </div>
              <span
                className={cn(
                  'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-xs border',
                  effectiveSelectedCurriculumId || partialAcknowledged
                    ? 'bg-success-soft text-success border-success/20'
                    : 'bg-surface-subtle text-text-muted border-border',
                )}
              >
                {evaluationMode === 'full'
                  ? effectiveSelectedCurriculumId
                    ? 'BOUND'
                    : 'REQUIRED'
                  : evaluationMode === 'partial'
                    ? partialAcknowledged
                      ? 'ACKNOWLEDGED'
                      : 'REQUIRED'
                    : 'PENDING'}
              </span>
            </li>
          </ul>
        </div>
      </aside>

      {/* ── RIGHT PANE: Pipeline Admission Docket ─────────────────────────── */}
      <main className="flex flex-col h-full min-h-0 bg-canvas overflow-y-auto p-6 sm:p-8 space-y-6">
        <h1 className="sr-only">Evaluation Setup</h1>

        {canConfigure && document && (
          <div className="space-y-6 max-w-4xl">
            {/* ── Step 01: Academic Program Binding ───────────────────────── */}
            <section
              aria-labelledby="step-01-heading"
              className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-5 items-center justify-center rounded-xs bg-primary/10 text-primary font-mono text-[11px] font-bold">
                    1
                  </span>
                  <div>
                    <h2
                      id="step-01-heading"
                      className="text-xs font-bold uppercase tracking-wider text-text"
                    >
                      Academic Program Confirmation
                    </h2>
                    <p className="text-xs text-text-muted mt-0.5">
                      Designate the official academic program for rubric weighting and specialist coordination.
                    </p>
                  </div>
                </div>

                {programConfirmed && (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                    <Check className="size-3.5" />
                    Confirmed
                  </span>
                )}
              </div>

              <div className="space-y-3 pt-1">
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

                <label className="flex items-center gap-3 text-xs font-medium text-text cursor-pointer select-none pt-1">
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
                    className="size-4 shrink-0 accent-primary rounded-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                    aria-describedby="program-confirm-help"
                  />
                  <span id="program-confirm-help" className="min-w-0 leading-relaxed">
                    I confirm this SLM belongs to the selected program.
                  </span>
                </label>
              </div>
            </section>

            {/* ── Step 02: Evaluation Protocol & Specialist Scope ─────────── */}
            <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-5 items-center justify-center rounded-xs bg-primary/10 text-primary font-mono text-[11px] font-bold">
                    2
                  </span>
                  <div>
                    <legend className="text-xs font-bold uppercase tracking-wider text-text px-0">
                      Select Evaluation Mode
                    </legend>
                    <p className="text-xs text-text-muted mt-0.5">
                      Choose between institutional accreditation compliance or advisory partial review.
                    </p>
                  </div>
                </div>

                {evaluationMode && (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                    <Check className="size-3.5" />
                    Protocol Chosen
                  </span>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-2 pt-1">
                {/* Protocol Card A: Full Evaluation */}
                <label
                  htmlFor="mode-full"
                  className={cn(
                    'relative flex flex-col justify-between p-4.5 rounded-sm border transition-all cursor-pointer select-none space-y-3',
                    evaluationMode === 'full'
                      ? 'border-primary bg-primary-soft/35 ring-2 ring-primary/30'
                      : 'border-border bg-surface hover:bg-surface-subtle hover:border-border-strong',
                    !programConfirmed && 'opacity-60 cursor-not-allowed',
                  )}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
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
                          className="size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                        />
                        <span className="text-sm font-bold text-text">Full Evaluation</span>
                      </div>
                      <Badge variant="success">4 Domains</Badge>
                    </div>

                    <p className="text-xs text-text-muted leading-relaxed">
                      Evaluates SME, Program Coordinator (Curriculum Alignment), GAD, and ITSO. Requires an active curriculum reference.
                    </p>
                  </div>

                  {/* Specialist Agent Scope Matrix */}
                  <div className="pt-1.5 space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                      Active Specialist Agents
                    </span>
                    <div className="grid grid-cols-2 gap-1.5 text-xs">
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        SME (Accuracy)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        Coordinator (Curriculum)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        GAD (Inclusivity)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        ITSO (IP Compliance)
                      </span>
                    </div>
                  </div>
                </label>

                {/* Protocol Card B: Partial Evaluation */}
                <label
                  htmlFor="mode-partial"
                  className={cn(
                    'relative flex flex-col justify-between p-4.5 rounded-sm border transition-all cursor-pointer select-none space-y-3',
                    evaluationMode === 'partial'
                      ? 'border-primary bg-primary-soft/35 ring-2 ring-primary/30'
                      : 'border-border bg-surface hover:bg-surface-subtle hover:border-border-strong',
                    !programConfirmed && 'opacity-60 cursor-not-allowed',
                  )}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
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
                          className="size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                        />
                        <span className="text-sm font-bold text-text">Partial Evaluation</span>
                      </div>
                      <Badge variant="warning">3 Domains</Badge>
                    </div>

                    <p className="text-xs text-text-muted leading-relaxed">
                      Evaluates SME, GAD, and ITSO domains only. The Program Coordinator review is skipped and the result is marked as partial.
                    </p>
                  </div>

                  {/* Specialist Agent Scope Matrix */}
                  <div className="pt-1.5 space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                      Active Specialist Agents
                    </span>
                    <div className="grid grid-cols-2 gap-1.5 text-xs">
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        SME (Accuracy)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text-muted line-through">
                        Coordinator (Skipped)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        GAD (Inclusivity)
                      </span>
                      <span className="inline-flex items-center gap-1.5 font-medium text-text">
                        <Check className="size-3.5 text-primary shrink-0" />
                        ITSO (IP Compliance)
                      </span>
                    </div>
                  </div>
                </label>
              </div>
            </fieldset>

            {/* ── Step 03A: Curriculum Reference Binding (Full Mode) ──────── */}
            {evaluationMode === 'full' && (
              <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex size-5 items-center justify-center rounded-xs bg-primary/10 text-primary font-mono text-[11px] font-bold">
                      3
                    </span>
                    <div>
                      <legend className="text-xs font-bold uppercase tracking-wider text-text px-0">
                        Select Curriculum Reference
                      </legend>
                      <p className="text-xs text-text-muted mt-0.5">
                        Anchor module learning outcomes and topics against an approved institutional curriculum map.
                      </p>
                    </div>
                  </div>

                  {Boolean(effectiveSelectedCurriculumId) && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                      <Check className="size-3.5" />
                      Reference Bound
                    </span>
                  )}
                </div>

                {isLoadingCurricula && (
                  <div
                    role="status"
                    aria-label="Loading curriculum references"
                    className="space-y-3 rounded-sm border border-border bg-surface-subtle p-4"
                  >
                    <Skeleton className="h-3.5 w-48 max-w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                )}

                {isCurriculaError && (
                  <div
                    role="alert"
                    className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs text-destructive"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="font-bold text-sm">Unable to load curriculum suggestions</p>
                        <p className="text-xs">
                          {String(getErrorMessage(curriculaError, 'Failed to fetch curriculum options.'))}
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
                )}

                {!isLoadingCurricula && !isCurriculaError && readyCurricula.length > 0 && (
                  <div className="space-y-2.5 pt-1">
                    {readyCurricula.map((curriculum) => {
                      const isSelected = effectiveSelectedCurriculumId === curriculum.documentId;
                      return (
                        <label
                          key={curriculum.documentId}
                          htmlFor={`curriculum-${curriculum.documentId}`}
                          className={cn(
                            'flex items-start gap-3.5 p-4 rounded-sm border transition-all cursor-pointer select-none',
                            isSelected
                              ? 'border-primary bg-primary-soft/35 ring-2 ring-primary/30'
                              : 'border-border bg-surface hover:bg-surface-subtle hover:border-border-strong',
                          )}
                        >
                          <input
                            type="radio"
                            id={`curriculum-${curriculum.documentId}`}
                            name="curriculum-selection"
                            value={curriculum.documentId}
                            checked={isSelected}
                            onChange={() => setSelectedCurriculumId(curriculum.documentId)}
                            className="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-bold text-text truncate">
                                {curriculum.title}
                              </span>
                              <Badge variant="success">Ready</Badge>
                            </div>
                            <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-text-muted">
                              <span>Program: {curriculum.program || selectedProgram}</span>
                              {Boolean(curriculum.matchReason) && (
                                <>
                                  <span>·</span>
                                  <span className="font-mono text-[11px] text-text-muted">
                                    Match: {curriculum.matchReason}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}

                {!isLoadingCurricula && !isCurriculaError && readyCurricula.length === 0 && (
                  <div className="rounded-sm border border-warning/30 bg-warning-soft p-4 text-xs text-warning leading-relaxed space-y-1">
                    <p className="font-bold text-sm">No ready curricula available for {selectedProgram}</p>
                    <p>
                      There are no published curriculum maps for {selectedProgram}. You can switch to Partial Evaluation above or upload a curriculum reference in the Admin Workspace.
                    </p>
                  </div>
                )}

                {unavailableCurricula.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider font-mono">
                      Unavailable Institutional References ({unavailableCurricula.length})
                    </p>
                    {unavailableCurricula.map((curriculum) => (
                      <label
                        key={curriculum.documentId}
                        htmlFor={`unavailable-curriculum-${curriculum.documentId}`}
                        className="flex items-start gap-3 p-3 rounded-sm border border-border bg-surface-subtle/50 opacity-60 cursor-not-allowed select-none"
                      >
                        <input
                          type="radio"
                          id={`unavailable-curriculum-${curriculum.documentId}`}
                          name="curriculum-selection"
                          disabled
                          aria-label={`Unavailable curriculum: ${curriculum.title}`}
                          className="mt-0.5 size-4 shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-semibold text-text truncate block">
                            {curriculum.title}
                          </span>
                          <p className="text-[11px] text-text-muted mt-0.5">
                            {curriculum.matchReason || 'Not ready for evaluation'}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>
            )}

            {/* ── Step 03B: Partial Evaluation Notice (Partial Mode) ───────── */}
            {evaluationMode === 'partial' && (
              <fieldset className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-4 shadow-none">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex size-5 items-center justify-center rounded-xs bg-warning/15 text-warning font-mono text-[11px] font-bold">
                      3
                    </span>
                    <div>
                      <legend className="text-xs font-bold uppercase tracking-wider text-text px-0">
                        Partial Evaluation Acknowledgement
                      </legend>
                      <p className="text-xs text-text-muted mt-0.5">
                        Acknowledge the exclusion of curriculum alignment and the advisory status of the result.
                      </p>
                    </div>
                  </div>

                  {partialAcknowledged && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                      <Check className="size-3.5" />
                      Acknowledged
                    </span>
                  )}
                </div>

                <div className="rounded-sm border border-warning/30 bg-warning-soft p-4 space-y-2 text-xs text-warning">
                  <div className="flex items-center gap-2">
                    <ShieldWarning className="size-4 shrink-0 text-warning" aria-hidden="true" />
                    <span className="font-bold text-sm">Coordinator Review Exclusion Notice</span>
                  </div>
                  <p className="leading-relaxed text-xs">
                    You have chosen to evaluate this SLM without an institutional curriculum reference. The Program Coordinator domain (Curriculum Map Alignment) will be excluded, and the resulting scorecard will be permanently marked as Partial.
                  </p>
                </div>

                <label className="flex items-start gap-3 text-xs font-semibold text-text cursor-pointer select-none pt-1">
                  <input
                    type="checkbox"
                    id="partial-acknowledge-checkbox"
                    checked={partialAcknowledged}
                    onChange={(e) => setPartialAcknowledged(e.target.checked)}
                    className="mt-0.5 size-4 shrink-0 accent-primary rounded-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                  />
                  <span className="min-w-0 leading-relaxed font-medium">
                    I understand that the Program Coordinator review will be skipped and acknowledge this partial evaluation.
                  </span>
                </label>
              </fieldset>
            )}

            {/* ── Step 04: Admission Console & Action Bar ─────────────────── */}
            <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-none">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-text">Admission Gate</span>
                  {canStart ? (
                    <Badge variant="success" withDot>
                      Ready for Admission
                    </Badge>
                  ) : (
                    <Badge variant="neutral">Prerequisites Incomplete</Badge>
                  )}
                </div>
                <p className="text-xs text-text-muted leading-relaxed">
                  {canStart
                    ? `All admission gates cleared. 4 specialist agents will analyze this module under the ${evaluationMode === 'full' ? 'Full 4-Domain' : 'Partial 3-Domain'} protocol.`
                    : !programConfirmed
                      ? 'Confirm the academic program in Step 01 to proceed.'
                      : !evaluationMode
                        ? 'Select an evaluation protocol in Step 02.'
                        : evaluationMode === 'full' && !effectiveSelectedCurriculumId
                          ? 'Select a ready curriculum reference to bind in Step 03.'
                          : 'Acknowledge the partial evaluation notice in Step 03 to proceed.'}
                </p>
              </div>

              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handleStart}
                disabled={!canStart || isSubmitting}
                className="shrink-0 font-bold uppercase tracking-wider text-xs h-10 px-6 gap-2"
              >
                {isSubmitting ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner className="size-4 animate-spin" aria-hidden="true" />
                    <span>Admitting…</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <Play className="size-3.5 fill-current" aria-hidden="true" weight="fill" />
                    <span>Start Evaluation</span>
                  </span>
                )}
              </Button>
            </div>

            {Boolean(submitError) && (
              <div
                role="alert"
                className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive flex items-center justify-between gap-4"
              >
                <span>{String(getErrorMessage(submitError, 'Failed to submit evaluation.'))}</span>
                <Button type="button" variant="destructive" size="sm" onClick={onRetrySubmit}>
                  Retry
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
