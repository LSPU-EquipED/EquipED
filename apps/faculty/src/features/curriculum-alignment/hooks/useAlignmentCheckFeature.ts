import { useMemo, useRef, useReducer } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@equiped/api-client';
import type { DropdownOption } from '@equiped/ui';
import { useCourses } from './useCourses';
import { useRunAlignmentCheck } from './useRunAlignmentCheck';
import { useAlignmentCheck } from './useAlignmentCheck';
import { useDocumentPages } from './useDocumentPages';
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
import type { SlmReadingPaneHandle } from '../components/SlmReadingPane';

export function useAlignmentCheckFeature() {
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
    queryFn: async () => {
      const firstPage = await documentsApi.listDocuments({ pageSize: 100 });
      if (firstPage.total <= 100) {
        return firstPage.items;
      }
      const allItems = [...firstPage.items];
      const totalPages = Math.ceil(firstPage.total / 100);
      for (let page = 2; page <= totalPages; page++) {
        const nextPage = await documentsApi.listDocuments({ page, pageSize: 100 });
        allItems.push(...nextPage.items);
      }
      return allItems;
    },
  });
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const runCheck = useRunAlignmentCheck();
  const activeCheck = useAlignmentCheck(activeCheckId);
  const { data: pagesData } = useDocumentPages(activeCheckId);

  const dispatchSelection = (action: AlignmentSelectionAction) => {
    if (runCheck.isPending) return;
    dispatch(action);
    runCheck.reset();
  };

  const documents = documentsData ?? [];
  const courses = coursesData?.items;

  const selectedDocument = documents.find((doc) => doc.documentId === documentId) ?? null;
  const selectedEligibility = useMemo(
    () => getAlignmentDocumentEligibility(selectedDocument),
    [selectedDocument],
  );

  const pickerDocuments = documents.filter((doc) => getAlignmentDocumentEligibility(doc).eligible);
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

  const handleClearActiveCheck = () => {
    dispatchSelection({ type: 'clearActiveCheck' });
  };

  const courseOptions = useMemo<DropdownOption[]>(
    () =>
      (courses ?? []).map((course) => ({
        value: course.course_id,
        label: `${course.course_code} — ${course.course_title}`,
      })),
    [courses],
  );

  return {
    documentId,
    courseId,
    activeCheckId,
    readingPaneRef,
    coursesLoading,
    runCheck,
    isChecking: runCheck.isPending,
    activeCheck,
    pagesData,
    selectedDocument,
    selectedEligibility,
    pickerDocuments,
    canRunCheck,
    runErrorState,
    activeLoadErrorState,
    activeFailureState,
    coverage,
    displayedSummary,
    isBoundedResult,
    coverageText,
    courseOptions,
    selectedDocumentSupportNotice,
    handleRun,
    handleSelectHistoryItem,
    handleDocumentChange,
    handleCourseChange,
    handleClearActiveCheck,
  };
}
