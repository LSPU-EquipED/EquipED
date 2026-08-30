import { useMemo, useRef, useReducer } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, Loader2 } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { AlignmentResultsTable } from '../components/AlignmentResultsTable';
import { AlignmentHistoryList } from '../components/AlignmentHistoryList';
import { SlmReadingPane, type SlmReadingPaneHandle } from '../components/SlmReadingPane';
import { CourseSelector } from '../components/CourseSelector';
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
        <h1 className="text-2xl font-bold text-text">Curriculum Alignment Check</h1>
        <p className="mt-1 text-sm text-text-muted">
          Check whether an SLM aligns with its course's curriculum map objectives.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-md border border-border bg-surface p-4">
        <div className="min-w-64 flex-1">
          <label className="mb-1.5 block text-xs font-semibold text-text">
            Document
          </label>
          <select
            value={documentId}
            onChange={(e) => handleDocumentChange(e.target.value)}
            className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
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

        <Button
          type="button"
          variant="primary"
          size="md"
          onClick={handleRun}
          disabled={!canRunCheck || runCheck.isPending}
          isLoading={runCheck.isPending}
        >
          Run Curriculum Alignment Check
        </Button>
      </div>

      {selectedDocumentSupportNotice ? (
        <div className="rounded-sm border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-semibold text-warning">
          <span className="inline-flex items-center gap-2">
            <Clock3 className="size-4 shrink-0" />
            {selectedDocumentSupportNotice}
          </span>
        </div>
      ) : null}

      {!documentId || !courseId ? (
        <div className="rounded-sm border border-border bg-primary-soft px-4 py-3 text-sm font-semibold text-primary">
          Pick a supported SLM and a course to run a new alignment check.
        </div>
      ) : null}

      {runCheck.isPending ? (
        <div className="flex items-center gap-2 rounded-sm border border-primary/20 bg-primary-soft p-3 text-sm font-semibold text-primary">
          <Loader2 className="size-4 animate-spin shrink-0 text-primary" />
          Running alignment check.
        </div>
      ) : null}

      {runErrorState ? (
        <div className="rounded-sm border border-destructive/20 bg-destructive-soft p-3 text-sm font-semibold text-destructive">
          <div className="mb-1 flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0" />
            <span>{runErrorState.title}</span>
          </div>
          <p className="text-xs font-medium">{runErrorState.message}</p>
          {runErrorState.kind === 'rate_limited' && runErrorState.retryAfterSeconds !== null ? (
            <p className="mt-1 text-xs font-bold tabular-nums">
              Retry in {runErrorState.retryAfterSeconds} second
              {runErrorState.retryAfterSeconds === 1 ? '' : 's'}.
            </p>
          ) : null}
        </div>
      ) : null}

      {documentId && courseId && !selectedDocumentSupportNotice && !runCheck.isPending && !runErrorState ? (
        <div className="rounded-sm border border-border bg-primary-soft px-4 py-3 text-sm font-semibold text-primary">
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
            className="self-start text-xs font-semibold uppercase tracking-wider text-primary hover:underline"
          >
            ← Back to history
          </button>

          {activeCheck.isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <Loader2 className="size-8 animate-spin text-primary" />
            </div>
          ) : null}

          {activeLoadErrorState ? (
            <div className="flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft p-3 text-sm font-semibold text-destructive">
              <AlertTriangle className="size-4 shrink-0" />
              <span>{activeLoadErrorState.title}</span>
            </div>
          ) : null}

          {activeLoadErrorState ? <p className="text-xs font-medium text-destructive">{activeLoadErrorState.message}</p> : null}

          {activeCheck.data && !activeCheck.data.success ? (
            <div className="flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft p-3 text-sm font-semibold text-destructive">
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
              <div className="rounded-sm border border-border bg-surface-subtle p-3 text-sm font-semibold text-text">
                Advisory only — human review is authoritative.
              </div>

              {isBoundedResult ? (
                <Badge variant="warning" className="self-start">
                  <CheckCircle2 className="size-3.5 mr-1" /> Partial - bounded coverage
                </Badge>
              ) : null}

              {coverage ? (
                <Badge variant="info" className="self-start">
                  {coverageText}
                </Badge>
              ) : null}

              {displayedSummary ? (
                <div className="grid gap-2 rounded-md border border-border bg-surface p-3 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-sm border border-border bg-surface-subtle p-2 text-sm">
                    <div className="text-xs text-text-muted">Match</div>
                    <div className="text-lg font-bold tabular-nums text-text">{displayedSummary.match}</div>
                  </div>
                  <div className="rounded-sm border border-border bg-surface-subtle p-2 text-sm">
                    <div className="text-xs text-text-muted">Under-developed</div>
                    <div className="text-lg font-bold tabular-nums text-text">{displayedSummary.under_developed}</div>
                  </div>
                  <div className="rounded-sm border border-border bg-surface-subtle p-2 text-sm">
                    <div className="text-xs text-text-muted">Over-developed</div>
                    <div className="text-lg font-bold tabular-nums text-text">{displayedSummary.over_developed}</div>
                  </div>
                  <div className="rounded-sm border border-border bg-surface-subtle p-2 text-sm">
                    <div className="text-xs text-text-muted">Not addressed</div>
                    <div className="text-lg font-bold tabular-nums text-text">{displayedSummary.not_addressed}</div>
                  </div>
                  <div className="rounded-sm border border-border bg-surface-subtle p-2 text-sm">
                    <div className="text-xs text-text-muted">Not observed</div>
                    <div className="text-lg font-bold tabular-nums text-text">{displayedSummary.not_observed}</div>
                  </div>
                </div>
              ) : null}

              <div className="grid flex-1 grid-cols-1 md:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)] gap-4 overflow-hidden">
                <div className="overflow-hidden rounded-md border border-border bg-surface">
                  <SlmReadingPane
                    ref={readingPaneRef}
                    pages={pagesData?.pages ?? []}
                  />
                </div>

                <div className="overflow-y-auto rounded-md border border-border bg-surface">
                  <div className="border-b border-border bg-surface-subtle px-4 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
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
