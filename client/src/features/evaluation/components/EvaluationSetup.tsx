import { useMemo } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  Loader2,
  Play,
  XCircle,
} from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { cn } from '@/shared/components/utils';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import {
  LSPU_SCC_COLLEGE_PROGRAMS,
  isLspuSccProgram,
} from '@/shared/constants/programs';
import type {
  ClientDocument,
  CurriculumSuggestionItem,
  CurriculumSuggestionResponse,
} from '@/shared/types/documents';

type EvaluationSetupProps = {
  document: ClientDocument | null | undefined;
  isLoadingDocument: boolean;
  documentError: unknown;
  selectedProgram: string;
  onSelectProgram: (program: string) => void;
  suggestionResponse: CurriculumSuggestionResponse | undefined;
  isLoadingSuggestions: boolean;
  isSuggestionsError: boolean;
  suggestionsError: unknown;
  selectedCurriculumId: string | null;
  onSelectCurriculum: (documentId: string) => void;
  hasReadyCurriculum: boolean;
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

function SuggestionRow({
  item,
  isSelected,
  isPreferred,
  isUnavailable,
  onSelect,
}: {
  item: CurriculumSuggestionItem;
  isSelected: boolean;
  isPreferred: boolean;
  isUnavailable: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={isUnavailable}
      className={cn(
        'flex w-full items-start gap-3 rounded-sm border px-4 py-3 text-left transition-colors',
        isUnavailable
          ? 'border-slate-200 bg-slate-50/50 opacity-70 cursor-not-allowed'
          : isSelected
            ? 'border-[#1b3b87] bg-[#1b3b87]/5'
            : 'border-slate-200 bg-white hover:bg-slate-50/60',
      )}
    >
      <span className="mt-0.5 shrink-0">
        {isUnavailable ? (
          <XCircle className="size-5 text-[#b91c1c]" aria-hidden="true" />
        ) : isSelected ? (
          <CheckCircle className="size-5 text-[#1b3b87]" aria-hidden="true" />
        ) : (
          <span className="block size-5 rounded-full border-2 border-slate-300" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-slate-900">{item.title}</span>
        <span className="mt-1 flex flex-wrap items-center gap-2">
          {isPreferred && !isUnavailable && (
            <span className="inline-flex items-center rounded-sm bg-[#1b3b87] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
              Preferred
            </span>
          )}
          <span
            className={cn(
              'inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
              isUnavailable
                ? 'bg-[#b91c1c]/10 text-[#b91c1c]'
                : 'bg-[#3b963e]/10 text-[#3b963e]',
            )}
          >
            {isUnavailable ? 'Not indexed' : 'Ready / Indexed'}
          </span>
        </span>
      </span>
      {!isUnavailable && (
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {item.program ?? ''}
        </span>
      )}
    </button>
  );
}

export function EvaluationSetup({
  document,
  isLoadingDocument,
  documentError,
  selectedProgram,
  onSelectProgram,
  suggestionResponse,
  isLoadingSuggestions,
  isSuggestionsError,
  suggestionsError,
  selectedCurriculumId,
  onSelectCurriculum,
  hasReadyCurriculum,
  isSubmitting,
  submitError,
  onStart,
  onRetrySubmit,
}: EvaluationSetupProps) {
  const programGroups = useMemo(() => {
    const detected = document?.program?.trim().toUpperCase();
    if (!detected || isLspuSccProgram(detected)) {
      return LSPU_SCC_COLLEGE_PROGRAMS;
    }

    return [
      {
        code: 'DETECTED',
        college: 'Detected from SLM',
        programs: [{ code: detected, name: 'Unlisted detected program' }],
      },
      ...LSPU_SCC_COLLEGE_PROGRAMS,
    ];
  }, [document?.program]);

  const readySuggestions = suggestionResponse?.curriculumSuggestions ?? [];
  const unavailableSuggestions = suggestionResponse?.unavailableCurricula ?? [];
  const preferredId = suggestionResponse?.preferredSuggestion?.documentId ?? null;
  const showSuggestions = selectedProgram.trim().length > 0;
  const canStart = hasReadyCurriculum && selectedCurriculumId != null && !isSubmitting;

  return (
    <section className="min-h-0 flex-1 overflow-y-auto bg-white">
      <div className="mx-auto grid max-w-2xl gap-8 px-6 py-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            New Evaluation
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Evaluation Setup</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">
            Confirm the academic program and CHED curriculum before starting the evaluation. The
            selected curriculum scopes the reference retrieval for this SLM.
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
          </div>
        ) : null}

        {!isLoadingDocument && !documentError ? (
          <div className="rounded-sm border border-slate-200 bg-white p-5">
            <ProgramSelector
              id="program-select"
              label="Academic Program"
              value={selectedProgram}
              onChange={onSelectProgram}
              groups={programGroups}
              placeholder={document?.program ? 'Confirm program' : 'Select a program'}
              hint={
                document?.program
                  ? 'The detected program is preselected. Change it if the SLM belongs to a different program.'
                  : 'The SLM did not identify a program. Select the owning program to find matching curricula.'
              }
            />
          </div>
        ) : null}

        {showSuggestions && !isLoadingSuggestions && isSuggestionsError ? (
          <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p>{getErrorMessage(suggestionsError, 'Unable to load curriculum suggestions.')}</p>
              </div>
            </div>
          </div>
        ) : null}

        {showSuggestions && isLoadingSuggestions ? (
          <div className="flex items-center gap-3 rounded-sm border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
            Looking up CHED curricula for {selectedProgram}…
          </div>
        ) : null}

        {showSuggestions && !isLoadingSuggestions && !isSuggestionsError ? (
          <div className="rounded-sm border border-slate-200 bg-white p-5">
            <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-slate-900">
              CHED Curriculum
            </h2>

            {readySuggestions.length > 0 ? (
              <div className="grid gap-3">
                {readySuggestions.map((item) => (
                  <SuggestionRow
                    key={item.documentId}
                    item={item}
                    isSelected={selectedCurriculumId === item.documentId}
                    isPreferred={preferredId === item.documentId}
                    isUnavailable={false}
                    onSelect={() => onSelectCurriculum(item.documentId)}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 px-4 py-4 text-sm text-[#1e293b]">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="flex-1">
                    <p className="font-semibold">No indexed curriculum for {selectedProgram}</p>
                    <p className="mt-1 leading-relaxed">
                      An admin must upload or rebuild the {selectedProgram} CHED curriculum
                      reference before evaluation can start.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {unavailableSuggestions.length > 0 ? (
              <div className="mt-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Unavailable curricula
                </p>
                <div className="grid gap-3">
                  {unavailableSuggestions.map((item) => (
                    <SuggestionRow
                      key={item.documentId}
                      item={item}
                      isSelected={false}
                      isPreferred={false}
                      isUnavailable
                      onSelect={() => undefined}
                    />
                  ))}
                </div>
                <p className="mt-3 text-xs font-medium text-slate-500">
                  These curricula are not ready for retrieval. Ask an admin to rebuild or re-upload
                  them.
                </p>
              </div>
            ) : null}
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

            {!hasReadyCurriculum && showSuggestions && !isLoadingSuggestions ? (
              <p className="text-center text-xs font-semibold text-slate-500">
                Start Evaluation is blocked until an indexed curriculum is available.
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
