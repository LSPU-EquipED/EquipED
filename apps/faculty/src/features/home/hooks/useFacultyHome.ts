import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import type { ClientDocument, DocumentStats } from '@equiped/types';
import { homeApi } from '../api/home.api';
import type { HomeEvaluationItem } from '../types';
import {
  deriveFacultyHomeData,
  isActiveEvaluationStatus,
  isProcessingDocument,
} from '../utils/homeData';

const EMPTY_DOCUMENTS: ClientDocument[] = [];
const EMPTY_EVALUATIONS: HomeEvaluationItem[] = [];

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

  const documents = documentsQuery.data?.items ?? EMPTY_DOCUMENTS;
  const evaluations = evaluationsQuery.data?.items ?? EMPTY_EVALUATIONS;

  const documentIds = useMemo(
    () => documents.slice(0, 5).map((d) => d.documentId),
    [documents],
  );

  const { latestEvalsByDocId, refetch: refetchLatestEvals } =
    useLatestEvaluations(documentIds);

  const isLoading =
    (documentsQuery.isLoading && !documentsQuery.data) ||
    (evaluationsQuery.isLoading && !evaluationsQuery.data);

  const isError = documentsQuery.isError || evaluationsQuery.isError;
  const error = documentsQuery.error || evaluationsQuery.error;

  const stats: DocumentStats = useMemo(() => {
    return {
      total: documentsQuery.data?.stats?.total ?? documents.length,
      ready:
        documentsQuery.data?.stats?.ready ??
        documents.filter((d) => d.processingStatus === 'PROCESSED').length,
      processing:
        documentsQuery.data?.stats?.processing ??
        documents.filter((d) => isProcessingDocument(d.processingStatus)).length,
      failed:
        documentsQuery.data?.stats?.failed ??
        documents.filter((d) => d.processingStatus === 'FAILED').length,
    };
  }, [documentsQuery.data?.stats, documents]);

  const homeData = useMemo(
    () =>
      deriveFacultyHomeData(documents, evaluations, latestEvalsByDocId),
    [documents, evaluations, latestEvalsByDocId],
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
    stats,
    homeData,
    evaluations,
    refetch,
  };
}
