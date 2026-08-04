// client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx
import { useMemo, useRef, useReducer } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, Loader2 } from 'lucide-react';
import { documentsApi } from '@/shared/api/documents.api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CourseSelector } from '../components/CourseSelector';
import { AlignmentResultsTable } from '../components/AlignmentResultsTable';
import { AlignmentHistoryList } from '../components/AlignmentHistoryList';
import { SlmReadingPane, type SlmReadingPaneHandle } from '../components/SlmReadingPane';
import { useCourses } from '../hooks/useCourses';
import { useRunAlignmentCheck } from '../hooks/useRunAlignmentCheck';
import { useAlignmentCheck } from '../hooks/useAlignmentCheck';
import { useDocumentPages } from '../hooks/useDocumentPages';
import {
  alignmentSelectionReducer,
  buildCoverageBanner,
  buildDisplayedSummary,
  getCoverageMetadata,
  getAlignmentDocumentEligibility,
  getAlignmentFailureState,
  getAlignmentRequestErrorState,
  type AlignmentSelectionAction,
  type AlignmentSelectionState,
} from '../utils/alignmentState';
import type { AlignmentCheckListItem } from '../types';

export function AlignmentCheckPage() {
  const [{ documentId, courseId, activeCheckId }, dispatch] = useReducer(
    alignmentSelectionReducer,
    {
      documentId: '',
      courseId: '',
      activeCheckId: null,
    } as AlignmentSelectionState,
  );

  const readingPaneRef = useRef<SlmReadingPaneHandle>(null);
  const queryClient = useQueryClient();

  const { data: documentsData } = useQuery({
    queryKey: ['curriculum-map', 'documents-for-picker'],
    queryFn: () => documentsApi.listDocuments({ pageSize: 100 }),
  });
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const runCheck = useRunAlignmentCheck();
  const activeCheck = useAlignmentCheck(activeCheckId);
  const { data: pagesData } = useDocumentPages(activeCheckId);

  const dispatchSelection = (action: AlignmentSelectionAction) => {
    dispatch(action);
    runCheck.reset();
  };

  const documents = documentsData?.items ?? [];
  const courses = coursesData?.items ?? [];

  const selectedDocument = documents.find((document) => document.documentId === documentId) ?? null;
  const selectedEligibility = useMemo(
    () => getAlignmentDocumentEligibility(selectedDocument),
    [selectedDocument],
  );

  const pickerDocuments = documents.filter((document) => getAlignmentDocumentEligibility(document).eligible);
  const canRunCheck = Boolean(documentId && courseId && selectedEligibility.eligible);

  const runErrorState = runCheck.isError ? getAlignmentRequestErrorState(runCheck.error) : null;
  const activeLoadErrorState = activeCheck.isError
    ? getAlignmentRequestErrorState(activeCheck.error)
    : null;
  const activeFailureState = getAlignmentFailureState(activeCheck.data ?? null);

  const coverage = useMemo(() => {
    if (!activeCheck.data) {
      return null;
    }

    return buildCoverageBanner(getCoverageMetadata(activeCheck.data));
  }, [activeCheck.data]);

  const displayedSummary = activeCheck.data ? buildDisplayedSummary(activeCheck.data) : null;
  const isBoundedResult = coverage?.kind === 'bounded';

  const coverageText = coverage?.text ?? '';

  const handleRun = () => {
    if (!canRunCheck) return;

    dispatchSelection({ type: 'clearActiveCheck' });

    runCheck.mutate(
      { documentId, courseId },
      {
        onSuccess: (data) => {
          dispatchSelection({ type: 'runCheckSuccess', checkId: data.check_id });
          queryClient.invalidateQueries({ queryKey: ['curriculum-map', 'checks'] });
        },
      },
    );
  };

  const handleSelectHistoryItem = (item: AlignmentCheckListItem) => {
    dispatchSelection({
      type: 'selectHistoryItem',
      documentId: item.document_id,
      courseId: item.course_id,
      checkId: item.check_id,
    });
  };

  const selectedDocumentSupportNotice =
    documentId && !selectedEligibility.eligible ? selectedEligibility.message : null;

  const handleDocumentChange = (nextDocumentId: string) => {
    dispatchSelection({ type: 'setDocument', documentId: nextDocumentId });
  };

  const handleCourseChange = (nextCourseId: string) => {
    dispatchSelection({ type: 'setCourse', courseId: nextCourseId });
  };

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-7">
      <div>
        <h1 className="text-lg font-bold text-slate-900">Curriculum Alignment Check</h1>
        <p className="text-sm text-slate-500">
          Check whether an SLM aligns with its course's curriculum map objectives.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-sm border border-slate-200 bg-white p-4">
        <div className="min-w-64 flex-1">
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
            Document
          </label>
          <select
            value={documentId}
            onChange={(e) => handleDocumentChange(e.target.value)}
            className="h-10 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
          >
            <option value="">Select a document...</option>
            {pickerDocuments.map((doc) => (
              <option key={doc.documentId} value={doc.documentId}>
                {doc.title}
              </option>
            ))}

            {documentId && !selectedEligibility.eligible && selectedDocument ? (
              <option value={selectedDocument.documentId} disabled>
                {selectedDocument.title} (not eligible)
              </option>
            ) : null}
          </select>
        </div>

        <div className="min-w-64 flex-1">
          <CourseSelector
            value={courseId}
            onChange={handleCourseChange}
            courses={courses}
            label="Course"
            disabled={coursesLoading}
          />
        </div>

        <button
          type="button"
          onClick={handleRun}
          disabled={!canRunCheck || runCheck.isPending}
          className="h-10 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-60"
        >
          Run Curriculum Alignment Check
        </button>
      </div>

      {selectedDocumentSupportNotice ? (
        <div className="rounded-sm border border-[#f2c811]/40 bg-[#f2c811]/10 px-4 py-3 text-sm font-semibold text-[#8a6d00]">
          <span className="inline-flex items-center gap-2">
            <Clock3 className="size-4 shrink-0" />
            {selectedDocumentSupportNotice}
          </span>
        </div>
      ) : null}

      {!documentId || !courseId ? (
        <div className="rounded-sm border border-[#1b3b87]/25 bg-[#1b3b87]/5 px-4 py-3 text-sm font-semibold text-[#1b3b87]">
          Pick a supported SLM and a course to run a new alignment check.
        </div>
      ) : null}

      {runCheck.isPending ? (
        <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
          <Loader2 className="size-4 animate-spin shrink-0" />
          Running alignment check.
        </div>
      ) : null}

      {runErrorState ? (
        <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
          <div className="mb-1 flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0" />
            <span>{runErrorState.title}</span>
          </div>
          <p className="text-xs font-medium">{runErrorState.message}</p>
          {runErrorState.kind === 'rate_limited' && runErrorState.retryAfterSeconds !== null ? (
            <p className="mt-1 text-xs font-bold">
              Retry in {runErrorState.retryAfterSeconds} second
              {runErrorState.retryAfterSeconds === 1 ? '' : 's'}.
            </p>
          ) : null}
        </div>
      ) : null}

      {documentId && courseId && !selectedDocumentSupportNotice && !runCheck.isPending && !runErrorState ? (
        <div className="rounded-sm border border-[#1b3b87]/25 bg-[#1b3b87]/5 px-4 py-3 text-sm font-semibold text-[#1b3b87]">
          {activeCheckId === null
            ? 'Selections ready. Run alignment check to load results.'
            : 'Alignment check loaded for selected pair.'}
        </div>
      ) : null}

      {!runCheck.isPending &&
      !runErrorState &&
      activeCheckId === null ? (
        <AlignmentHistoryList onSelect={handleSelectHistoryItem} />
      ) : null}

      {activeCheckId !== null && !runCheck.isPending ? (
        <div className="flex flex-1 flex-col gap-3 overflow-hidden">
          <button
            type="button"
            onClick={() => dispatchSelection({ type: 'clearActiveCheck' })}
            className="self-start text-xs font-bold uppercase tracking-wider text-[#1b3b87] hover:underline"
          >
            ← Back to history
          </button>

          {activeCheck.isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
            </div>
          ) : null}

          {activeLoadErrorState ? (
            <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
              <AlertTriangle className="size-4 shrink-0" />
              <span>{activeLoadErrorState.title}</span>
            </div>
          ) : null}

          {activeLoadErrorState ? <p className="text-xs font-medium">{activeLoadErrorState.message}</p> : null}

          {activeCheck.data && !activeCheck.data.success ? (
            <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
              <AlertTriangle className="size-4 shrink-0" />
              <div>
                <div className="flex items-center gap-2">
                  <span>{activeFailureState?.title ?? 'Alignment check failed'}</span>
                </div>
                <p className="text-xs font-medium">{activeFailureState?.message ?? 'Unknown failure'}</p>
              </div>
            </div>
          ) : null}

          {activeCheck.data && activeCheck.data.success ? (
            <>
              <div className="rounded-sm border border-slate-200 bg-[#1b3b87]/5 p-3 text-sm font-semibold text-slate-800">
                Advisory only — human review is authoritative.
              </div>

              {isBoundedResult ? (
                <div className="inline-flex items-center gap-2 self-start rounded-sm border border-[#f2c811]/40 bg-[#f2c811]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-[#8a6d00]">
                  <CheckCircle2 className="size-3.5" /> Partial - bounded coverage
                </div>
              ) : null}

              {coverage ? (
                <div className="inline-flex items-center gap-2 self-start rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-[#1b3b87]">
                  <span>{coverageText}</span>
                </div>
              ) : null}

              {displayedSummary ? (
                <div className="grid gap-2 rounded-sm border border-slate-200 bg-white p-3 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-sm border border-slate-200 bg-slate-50 p-2 text-sm">
                    <div className="text-xs text-slate-500">Match</div>
                    <div className="text-lg font-bold text-slate-800">{displayedSummary.match}</div>
                  </div>
                  <div className="rounded-sm border border-slate-200 bg-slate-50 p-2 text-sm">
                    <div className="text-xs text-slate-500">Under-developed</div>
                    <div className="text-lg font-bold text-slate-800">{displayedSummary.under_developed}</div>
                  </div>
                  <div className="rounded-sm border border-slate-200 bg-slate-50 p-2 text-sm">
                    <div className="text-xs text-slate-500">Over-developed</div>
                    <div className="text-lg font-bold text-slate-800">{displayedSummary.over_developed}</div>
                  </div>
                  <div className="rounded-sm border border-slate-200 bg-slate-50 p-2 text-sm">
                    <div className="text-xs text-slate-500">Not addressed</div>
                    <div className="text-lg font-bold text-slate-800">{displayedSummary.not_addressed}</div>
                  </div>
                  <div className="rounded-sm border border-slate-200 bg-slate-50 p-2 text-sm">
                    <div className="text-xs text-slate-500">Not observed</div>
                    <div className="text-lg font-bold text-slate-800">{displayedSummary.not_observed}</div>
                  </div>
                </div>
              ) : null}

              <div className="grid flex-1 grid-cols-1 md:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)] gap-4 overflow-hidden">
                <div className="overflow-hidden rounded-sm border border-slate-200">
                  <SlmReadingPane
                    ref={readingPaneRef}
                    pages={pagesData?.pages ?? []}
                  />
                </div>

                <div className="overflow-y-auto rounded-sm border border-slate-200 bg-white">
                  <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Objectives
                  </div>

                  <AlignmentResultsTable
                    objectiveResults={activeCheck.data.objective_results}
                    coverageScope={
                      coverage?.kind === 'bounded' ? 'bounded' : coverage?.kind === 'legacy' ? 'legacy_unknown' : 'full'
                    }
                    onEvidenceClick={(pageNumber, evidenceText) =>
                      readingPaneRef.current?.scrollToPage(pageNumber, evidenceText)
                    }
                  />
                </div>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
