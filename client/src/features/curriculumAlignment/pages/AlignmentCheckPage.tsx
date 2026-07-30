// client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx
import { useRef, useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { documentsApi } from '@/shared/api/documents.api';
import { useQuery } from '@tanstack/react-query';
import { CourseSelector } from '../components/CourseSelector';
import { AlignmentResultsTable } from '../components/AlignmentResultsTable';
import { SlmReadingPane, type SlmReadingPaneHandle } from '../components/SlmReadingPane';
import { useCourses } from '../hooks/useCourses';
import { useRunAlignmentCheck } from '../hooks/useRunAlignmentCheck';
import { useDocumentPages } from '../hooks/useDocumentPages';

export function AlignmentCheckPage() {
  const [documentId, setDocumentId] = useState('');
  const [courseId, setCourseId] = useState('');
  const readingPaneRef = useRef<SlmReadingPaneHandle>(null);

  const { data: documentsData } = useQuery({
    queryKey: ['curriculum-map', 'documents-for-picker'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', pageSize: 100 }),
  });
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const runCheck = useRunAlignmentCheck();
  const { data: pagesData } = useDocumentPages(runCheck.data?.check_id ?? null);

  const documents = documentsData?.items ?? [];
  const courses = coursesData?.items ?? [];

  const handleRun = () => {
    if (!documentId || !courseId) return;
    runCheck.mutate({ documentId, courseId });
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
            onChange={(e) => setDocumentId(e.target.value)}
            className="h-10 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
          >
            <option value="">Select a document...</option>
            {documents.map((doc) => (
              <option key={doc.documentId} value={doc.documentId}>
                {doc.title}
              </option>
            ))}
          </select>
        </div>

        <div className="min-w-64 flex-1">
          <CourseSelector
            value={courseId}
            onChange={setCourseId}
            courses={courses}
            label="Course"
            disabled={coursesLoading}
          />
        </div>

        <button
          type="button"
          onClick={handleRun}
          disabled={!documentId || !courseId || runCheck.isPending}
          className="h-10 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-60"
        >
          Run Curriculum Alignment Check
        </button>
      </div>

      {runCheck.isPending ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
        </div>
      ) : null}

      {runCheck.isError ? (
        <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
          <AlertTriangle className="size-4 shrink-0" />
          {getErrorMessage(runCheck.error, 'Curriculum alignment check failed.')}
        </div>
      ) : null}

      {runCheck.data && !runCheck.data.success ? (
        <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
          <AlertTriangle className="size-4 shrink-0" />
          {runCheck.data.error_message ?? 'Curriculum alignment check failed.'}
        </div>
      ) : null}

      {runCheck.data && runCheck.data.success ? (
        <div className="grid flex-1 grid-cols-2 gap-4 overflow-hidden">
          <div className="overflow-hidden rounded-sm border border-slate-200">
            <SlmReadingPane ref={readingPaneRef} pages={pagesData?.pages ?? []} />
          </div>
          <div className="overflow-y-auto rounded-sm border border-slate-200 bg-white">
            <AlignmentResultsTable
              objectiveResults={runCheck.data.objective_results}
              onEvidenceClick={(pageNumber) => readingPaneRef.current?.scrollToPage(pageNumber)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
