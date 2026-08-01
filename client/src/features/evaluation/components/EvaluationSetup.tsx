import { useState } from 'react';
import { AlertTriangle, BookOpen, Loader2, Play, ShieldAlert } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import { canStartConfirmedPartial } from '@/features/evaluation/utils/setupState';
import type { ClientDocument } from '@/shared/types/documents';

type EvaluationSetupProps = {
  document: ClientDocument | null | undefined;
  isLoadingDocument: boolean;
  documentError: unknown;
  selectedProgram: string;
  detectedProgram: string | null;
  onSelectProgram: (program: string) => void;
  isResolveError: boolean;
  resolveError: unknown;
  isSubmitting: boolean;
  submitError: unknown;
  onStart: () => void;
  onRetrySubmit: () => void;
};

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
  isSubmitting,
  submitError,
  onStart,
  onRetrySubmit,
}: EvaluationSetupProps) {
  const [programConfirmed, setProgramConfirmed] = useState(false);
  const [partialAcknowledged, setPartialAcknowledged] = useState(false);

  const canStart = canStartConfirmedPartial({
    program: selectedProgram,
    programConfirmed,
    partialAcknowledged,
    isSubmitting,
  });

  return (
    <section className="min-h-0 flex-1 overflow-y-auto bg-white">
      <div className="mx-auto grid max-w-2xl gap-8 px-6 py-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            New Evaluation
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Evaluation Setup</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">
            Confirm the academic program and acknowledge the partial review before starting the
            evaluation. Nothing is submitted until you choose to start.
          </p>
        </div>

        {isLoadingDocument ? (
          <div className="flex items-center gap-3 rounded-sm border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
            Loading SLM metadata…
          </div>
        ) : null}

        {documentError ? (
          <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]">
            {getErrorMessage(documentError, 'Unable to load the selected document.')}
          </div>
        ) : null}

        {isResolveError ? (
          <div className="rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 px-4 py-3 text-sm text-[#1e293b]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-semibold">Could not check for existing evaluations</p>
                <p className="mt-1 leading-relaxed">
                  {getErrorMessage(
                    resolveError,
                    'The lookup failed, so you can start a fresh evaluation below.',
                  )}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {!isLoadingDocument && !documentError && document ? (
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
                <MetadataRow label="Program" value={document.program.trim().toUpperCase()} />
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

        {!isLoadingDocument && !documentError ? (
          <div className="rounded-sm border border-slate-200 bg-white p-5">
            <ProgramSelector
              id="program-select"
              label="Academic Program"
              value={selectedProgram}
              onChange={onSelectProgram}
              groups={LSPU_SCC_COLLEGE_PROGRAMS}
              placeholder="Select a program"
              hint={
                detectedProgram
                  ? 'The detected program is preselected as a suggestion. Change it if it is not correct, then confirm below.'
                  : 'No program was detected in the SLM. Select the owning program, then confirm below.'
              }
            />
            <label className="mt-4 flex items-start gap-3 border-t border-slate-100 pt-4 text-sm font-semibold text-slate-900">
              <input
                type="checkbox"
                checked={programConfirmed}
                onChange={(event) => setProgramConfirmed(event.target.checked)}
                className="mt-1 size-4 shrink-0 accent-[#1b3b87]"
                aria-describedby="program-confirm-help"
              />
              <span id="program-confirm-help" className="min-w-0 leading-relaxed">
                I confirm this SLM belongs to the selected program.
              </span>
            </label>
          </div>
        ) : null}

        {!isLoadingDocument && !documentError ? (
          <div className="rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-5">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 size-5 shrink-0 text-[#1e293b]" aria-hidden="true" />
              <div className="flex-1">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                  Partial review
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-[#1e293b]">
                  This evaluation runs without a curriculum reference. The Program Coordinator
                  review will be skipped; SME, GAD, and ITSO will still review the SLM. The result
                  is reported as partial and remains advisory.
                </p>
              </div>
            </div>
            <label className="mt-4 flex items-start gap-3 border-t border-[#f2c811]/40 pt-4 text-sm font-semibold text-slate-900">
              <input
                type="checkbox"
                checked={partialAcknowledged}
                onChange={(event) => setPartialAcknowledged(event.target.checked)}
                className="mt-1 size-4 shrink-0 accent-[#1b3b87]"
                aria-describedby="partial-acknowledgement-help"
              />
              <span id="partial-acknowledgement-help" className="min-w-0 leading-relaxed">
                I understand that the Program Coordinator review will be skipped and the result will
                be marked as a partial evaluation.
              </span>
            </label>
          </div>
        ) : null}

        {!isLoadingDocument && !documentError ? (
          <div className="space-y-4">
            {submitError ? (
              <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="flex-1">
                    <p>{getErrorMessage(submitError, 'Failed to start evaluation.')}</p>
                    <button
                      type="button"
                      onClick={onRetrySubmit}
                      className="mt-2 inline-flex h-8 items-center justify-center border border-[#b91c1c]/30 px-3 text-xs font-bold uppercase tracking-wide text-[#b91c1c] transition-colors hover:bg-[#b91c1c]/10 rounded-sm focus:outline-none focus:ring-2 focus:ring-[#b91c1c]/30"
                    >
                      Retry
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            <button
              type="button"
              onClick={onStart}
              disabled={!canStart}
              className="inline-flex h-11 w-full items-center justify-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 rounded-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Starting evaluation…
                </>
              ) : (
                <>
                  <Play className="size-4" aria-hidden="true" />
                  Start Evaluation
                </>
              )}
            </button>

            {!canStart && !isSubmitting ? (
              <p className="text-center text-xs font-medium text-slate-500 leading-relaxed">
                {selectedProgram
                  ? 'Confirm the program and acknowledge the partial review to start.'
                  : 'Select and confirm a program to start.'}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
