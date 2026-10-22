import { useMemo, useRef, useReducer } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi, getErrorMessage } from "@equiped/api-client";
import type { DropdownOption } from "@equiped/ui";
import { useCourses } from "./useCourses";
import { useRunAlignmentCheck } from "./useRunAlignmentCheck";
import { useAlignmentCheck } from "./useAlignmentCheck";
import { useDocumentPages } from "./useDocumentPages";
import {
  alignmentSelectionReducer,
  buildCoverageBanner,
  buildDisplayedSummary,
  getCoverageMetadata,
  getAlignmentDocumentEligibility,
  getAlignmentCoursesForDocument,
  getAlignmentFailureState,
  getAlignmentRequestErrorState,
  type AlignmentSelectionAction,
  type AlignmentSelectionState,
} from "../utils/alignmentState";
import type { AlignmentCheckListItem } from "../types";
import type { SlmReadingPaneHandle } from "../components/SlmReadingPane";

export function useAlignmentCheckFeature() {
  const [{ documentId, courseId, activeCheckId }, dispatch] = useReducer(
    alignmentSelectionReducer,
    {
      documentId: "",
      courseId: "",
      activeCheckId: null,
    } as AlignmentSelectionState,
  );

  const readingPaneRef = useRef<SlmReadingPaneHandle>(null);
  const queryClient = useQueryClient();

  const documentsQuery = useQuery({
    queryKey: ["curriculum-map", "documents-for-picker"],
    queryFn: async () => {
      const firstPage = await documentsApi.listDocuments({ pageSize: 100 });
      if (firstPage.total <= 100) {
        return firstPage.items;
      }
      const allItems = [...firstPage.items];
      const totalPages = Math.ceil(firstPage.total / 100);
      for (let page = 2; page <= totalPages; page++) {
        const nextPage = await documentsApi.listDocuments({
          page,
          pageSize: 100,
        });
        allItems.push(...nextPage.items);
      }
      return allItems;
    },
  });
  const coursesQuery = useCourses();
  const runCheck = useRunAlignmentCheck();
  const activeCheck = useAlignmentCheck(activeCheckId);
  const { data: pagesData } = useDocumentPages(activeCheckId);

  const dispatchSelection = (action: AlignmentSelectionAction) => {
    if (runCheck.isPending) return;
    dispatch(action);
    runCheck.reset();
  };

  const documents = documentsQuery.data ?? [];
  const courses = coursesQuery.data?.items;

  const selectedDocument =
    documents.find((doc) => doc.documentId === documentId) ?? null;
  const selectedEligibility = useMemo(
    () => getAlignmentDocumentEligibility(selectedDocument),
    [selectedDocument],
  );

  const pickerDocuments = documents.filter(
    (doc) => getAlignmentDocumentEligibility(doc).eligible,
  );
  const compatibleCourses = useMemo(
    () => getAlignmentCoursesForDocument(courses ?? [], selectedDocument),
    [courses, selectedDocument],
  );
  const canRunCheck = Boolean(
    documentId && selectedEligibility.eligible
      && compatibleCourses.some((course) => course.course_id === courseId),
  );

  const runErrorState = runCheck.isError
    ? getAlignmentRequestErrorState(runCheck.error)
    : null;
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

  const displayedSummary = activeCheck.data
    ? buildDisplayedSummary(activeCheck.data)
    : null;
  const isBoundedResult = coverage?.kind === "bounded";
  const coverageText = coverage?.text ?? "";

  const handleRun = () => {
    if (!canRunCheck) return;

    dispatchSelection({ type: "clearActiveCheck" });

    runCheck.mutate(
      { documentId, courseId },
      {
        onSuccess: (data) => {
          dispatchSelection({
            type: "runCheckSuccess",
            checkId: data.check_id,
          });
          queryClient.invalidateQueries({
            queryKey: ["curriculum-map", "checks"],
          });
        },
      },
    );
  };

  const handleSelectHistoryItem = (item: AlignmentCheckListItem) => {
    dispatchSelection({
      type: "selectHistoryItem",
      documentId: item.document_id,
      courseId: item.course_id,
      checkId: item.check_id,
    });
  };

  const handleDocumentChange = (nextDocumentId: string) => {
    dispatchSelection({ type: "setDocument", documentId: nextDocumentId });
  };

  const handleCourseChange = (nextCourseId: string) => {
    dispatchSelection({ type: "setCourse", courseId: nextCourseId });
  };

  const handleClearActiveCheck = () => {
    dispatchSelection({ type: "clearActiveCheck" });
  };

  const courseOptions = useMemo<DropdownOption[]>(
    () =>
      compatibleCourses.map((course) => ({
        value: course.course_id,
        label: `${course.course_code} — ${course.course_title}`,
      })),
    [compatibleCourses],
  );

  return {
    documentId,
    courseId,
    activeCheckId,
    readingPaneRef,
    documentsLoading: documentsQuery.isLoading,
    coursesLoading: coursesQuery.isLoading,
    documentsError: documentsQuery.isError
      ? getErrorMessage(documentsQuery.error, "Unable to load modules.")
      : null,
    coursesError: coursesQuery.isError
      ? getErrorMessage(coursesQuery.error, "Unable to load courses.")
      : null,
    retryDocuments: () => {
      void documentsQuery.refetch();
    },
    retryCourses: () => {
      void coursesQuery.refetch();
    },
    runCheck,
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
    handleRun,
    handleSelectHistoryItem,
    handleDocumentChange,
    handleCourseChange,
    handleClearActiveCheck,
  };
}
