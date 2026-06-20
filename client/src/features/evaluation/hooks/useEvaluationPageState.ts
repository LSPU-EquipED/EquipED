import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import { useFetch } from '@/shared/hooks/useFetch';
import type { ClientDocument, ClientDocumentChunk } from '@/shared/types/documents';
import { evaluationApi } from '@/features/evaluation/api/evaluation.api';
import { useSubmitEvaluation } from '@/features/upload/hooks/useSubmitEvaluation';
import type { EvaluationStatusResponse } from '@/features/evaluation/types';

const EVAL_STORAGE_PREFIX = 'equiped_eval_';

type DocumentTextGroup = {
  documentId: string;
  chunks: ClientDocumentChunk[];
};

function buildDocumentTextGroups(document: ClientDocument | null): DocumentTextGroup[] {
  if (!document) {
    return [];
  }

  const groups = new Map<string, ClientDocumentChunk[]>();

  for (const chunk of document.chunks) {
    const chunks = groups.get(chunk.documentId) ?? [];
    chunks.push(chunk);
    groups.set(chunk.documentId, chunks);
  }

  return Array.from(groups.entries())
    .sort(([leftDocumentId], [rightDocumentId]) => leftDocumentId.localeCompare(rightDocumentId))
    .map(([documentId, chunks]) => ({
      documentId,
      chunks: [...chunks].sort((left, right) => left.pageNumber - right.pageNumber),
    }));
}

export function useEvaluationPageState(documentId?: string) {
  const queryClient = useQueryClient();
  const submitEvaluation = useSubmitEvaluation();
  const { data: document, error, isLoading, execute } = useFetch(documentsApi.getDocument);

  const storageKey = documentId ? `${EVAL_STORAGE_PREFIX}${documentId}` : null;
  const submitAttemptedRef = useRef(false);
  const hasRecoveredRef = useRef(false);

  // Document fetch effect
  useEffect(() => {
    if (!documentId) {
      return;
    }

    void execute(documentId).catch(() => undefined);
  }, [documentId, execute]);

  // Resolve evaluation
  const {
    data: evaluationId,
    isLoading: isResolvingEval,
    isError: isResolveError,
    error: resolveError,
    refetch: refetchResolve,
  } = useQuery({
    queryKey: ['resolve-evaluation', documentId],
    queryFn: async () => {
      if (!documentId) throw new Error('No document ID');

      if (storageKey) {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) return stored;
      }

      const list = await evaluationApi.listEvaluations(documentId);
      if (list.items.length > 0) {
        const nonFailed = list.items
          .filter((item) => item.status !== 'FAILED')
          .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime());

        if (nonFailed.length > 0) {
          const id = nonFailed[0].evaluation_id;
          if (storageKey) {
            sessionStorage.setItem(storageKey, id);
          }
          return id;
        }
      }

      return null;
    },
    enabled: !!documentId,
    staleTime: Infinity,
    retry: false,
  });

  const submitFreshEvaluation = useCallback(() => {
    if (!documentId || submitEvaluation.isPending || submitAttemptedRef.current) return;

    submitAttemptedRef.current = true;
    submitEvaluation
      .mutateAsync({ document_id: documentId })
      .then((result) => {
        if (storageKey) {
          sessionStorage.setItem(storageKey, result.evaluation_id);
        }
        void queryClient.invalidateQueries({
          queryKey: ['resolve-evaluation', documentId],
        });
      })
      .catch(() => {
        // Intentionally do NOT reset submitAttemptedRef here.
        // The UI shows the error and waits for an explicit user retry.
      });
  }, [documentId, submitEvaluation, storageKey, queryClient]);

  // Auto-submit a fresh evaluation once when resolve returns null
  // and no submission has been attempted for this resolution cycle.
  useEffect(() => {
    if (evaluationId !== null) {
      submitAttemptedRef.current = false;
      return;
    }
    if (!documentId) return;
    if (submitEvaluation.isPending) return;
    if (submitAttemptedRef.current) return;

    submitFreshEvaluation();
  }, [evaluationId, documentId, submitEvaluation.isPending, submitFreshEvaluation]);

  // Results query
  const {
    data: results,
    refetch: refetchResults,
    isError: isResultsError,
    error: resultsError,
  } = useQuery({
    queryKey: ['evaluation-results', evaluationId],
    queryFn: () => evaluationApi.getEvaluationResults(evaluationId!),
    enabled: !!evaluationId,
    refetchInterval: (query) => {
      const evalStatus = (query.state.data as { evaluation_status?: string } | undefined)
        ?.evaluation_status;
      if (evalStatus === 'COMPLETED' || evalStatus === 'FAILED') {
        return false;
      }
      return 3000;
    },
    retry: 1,
  });

  // Status query
  const { data: status } = useQuery<EvaluationStatusResponse>({
    queryKey: ['evaluation-status', evaluationId],
    queryFn: () => evaluationApi.getEvaluationStatus(evaluationId!),
    enabled: !!evaluationId,
    refetchInterval: (query) => {
      const nextStatus = query.state.data?.status;
      if (nextStatus === 'COMPLETED' || nextStatus === 'FAILED') {
        return false;
      }

      return 3000;
    },
  });

  // Status change -> refetch results
  useEffect(() => {
    if (status?.status === 'COMPLETED' || status?.status === 'FAILED') {
      void refetchResults();
    }
  }, [status?.status, refetchResults]);

  // Derived state
  const isTerminal = status?.status === 'COMPLETED' || status?.status === 'FAILED';
  const hasResults = !!results && Object.keys(results.domain_scores).length > 0;
  const isInProgress = (!!evaluationId && !isTerminal) || !!submitEvaluation.isPending;
  const isFailedWithResults = status?.status === 'FAILED' && hasResults;

  // Stale-cache recovery: if downstream queries fail for a terminal eval,
  // clear the cached id and re-resolve once.
  useEffect(() => {
    if (!isResultsError || !isTerminal || !evaluationId) return;
    if (hasRecoveredRef.current) return;

    hasRecoveredRef.current = true;
    if (storageKey) {
      sessionStorage.removeItem(storageKey);
    }
    void queryClient.invalidateQueries({
      queryKey: ['resolve-evaluation', documentId],
    });
  }, [isResultsError, isTerminal, evaluationId, storageKey, queryClient, documentId]);

  const handleRetryEvaluation = useCallback(() => {
    if (storageKey) {
      sessionStorage.removeItem(storageKey);
    }
    submitAttemptedRef.current = false;
    hasRecoveredRef.current = false;
    void refetchResolve();
  }, [storageKey, refetchResolve]);

  const handleRetrySubmit = useCallback(() => {
    submitAttemptedRef.current = false;
    submitFreshEvaluation();
  }, [submitFreshEvaluation]);

  // Document derived
  const documentTextGroups = useMemo(() => buildDocumentTextGroups(document), [document]);
  const chunkMap = useMemo(() => {
    const map = new Map<string, ClientDocumentChunk>();
    for (const group of documentTextGroups) {
      for (const chunk of group.chunks) {
        map.set(chunk.chunkId, chunk);
      }
    }
    return map;
  }, [documentTextGroups]);

  return {
    document,
    isLoadingDocument: isLoading,
    documentError: error,
    evaluationId,
    isResolvingEval,
    isResolveError,
    resolveError,
    refetchResolve,
    submitEvaluation,
    results,
    refetchResults,
    isResultsError,
    resultsError,
    status,
    isTerminal,
    hasResults,
    isInProgress,
    isFailedWithResults,
    handleRetryEvaluation,
    handleRetrySubmit,
    documentTextGroups,
    chunkMap,
  };
}
