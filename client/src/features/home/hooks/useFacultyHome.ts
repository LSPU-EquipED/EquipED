import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import { homeApi } from '../api/home.api';
import {
  deriveFacultyHomeData,
  isActiveEvaluationStatus,
  isProcessingDocument,
} from '../utils/homeData';

export function useFacultyHome() {
  const documentsQuery = useQuery({
    queryKey: ['documents', { sourceType: 'slm' }],
    queryFn: () => homeApi.listSlms(),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((d) => isProcessingDocument(d.processingStatus)) ? 4000 : false;
    },
  });

  const evaluationsQuery = useQuery({
    queryKey: ['evaluations', { pageSize: 20 }],
    queryFn: () => homeApi.listEvaluations(20),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((e) => isActiveEvaluationStatus(e.status)) ? 4000 : false;
    },
  });

  const documents = documentsQuery.data?.items ?? [];
  const evaluations = evaluationsQuery.data?.items ?? [];

  const documentIds = useMemo(
    () => documents.slice(0, 5).map((d) => d.documentId),
    [documents],
  );

  const {
    latestEvalsByDocId,
    isLoading: isLatestEvalsLoading,
    isError: isLatestEvalsError,
    isSuccess: isLatestEvalsSuccess,
    refetch: refetchLatestEvals,
  } = useLatestEvaluations(documentIds);

  const latestEvalsState = useMemo(
    () => ({
      isLoading: isLatestEvalsLoading,
      isError: isLatestEvalsError,
      isSuccess: isLatestEvalsSuccess,
    }),
    [isLatestEvalsLoading, isLatestEvalsError, isLatestEvalsSuccess],
  );

  const isLoading =
    (documentsQuery.isLoading && !documentsQuery.data) ||
    (evaluationsQuery.isLoading && !evaluationsQuery.data);

  const isError = documentsQuery.isError || evaluationsQuery.isError;
  const error = documentsQuery.error || evaluationsQuery.error;

  const homeData = useMemo(
    () =>
      deriveFacultyHomeData(
        documents,
        evaluations,
        latestEvalsByDocId,
        isLatestEvalsSuccess,
      ),
    [documents, evaluations, latestEvalsByDocId, isLatestEvalsSuccess],
  );

  const refetch = () => {
    void documentsQuery.refetch();
    void evaluationsQuery.refetch();
    void refetchLatestEvals();
  };

  return {
    isLoading,
    isError,
    error,
    homeData,
    documents,
    evaluations,
    latestEvalsByDocId,
    latestEvalsState,
    refetch,
  };
}
