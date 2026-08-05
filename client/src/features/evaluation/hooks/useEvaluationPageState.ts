import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import { useFetch } from '@/shared/hooks/useFetch';
import { isLspuSccProgram } from '@/shared/constants/programs';
import type { ClientDocument, ClientDocumentChunk } from '@/shared/types/documents';
import { evaluationApi } from '@/features/evaluation/api/evaluation.api';
import { useSubmitEvaluation } from '@/features/upload/hooks/useSubmitEvaluation';
import { resolveExistingEvaluation } from '@/features/evaluation/utils/setupState';
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
  const {
    data: document,
    error,
    isLoading: isLoadingDocument,
    execute,
  } = useFetch(documentsApi.getDocument);

  const storageKey = documentId ? `${EVAL_STORAGE_PREFIX}${documentId}` : null;
  const hasRecoveredRef = useRef(false);

  const [selectedProgram, setSelectedProgram] = useState<string>('');

  // A program detected in the SLM is a suggestion only: it is shown in the
  // selector until the user replaces it, but the user must explicitly confirm
  // it before submission. Unlisted detections never auto-fill the selector.
  const detectedProgram = document?.program?.trim().toUpperCase() ?? null;
  const effectiveProgram =
    selectedProgram || (detectedProgram && isLspuSccProgram(detectedProgram) ? detectedProgram : '');

  // Document fetch effect
  useEffect(() => {
    if (!documentId) {
      return;
    }

    void execute(documentId).catch(() => undefined);
  }, [documentId, execute]);

  // Resolve evaluation. Backend list is authoritative; sessionStorage is only a
  // cache updated after the backend confirms an existing evaluation. A stale
  // cached id must not bypass setup when no evaluation exists.
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

      const list = await evaluationApi.listEvaluations(documentId);
      const resolvedId = resolveExistingEvaluation(list.items);
      if (resolvedId) {
        if (storageKey) {
          sessionStorage.setItem(storageKey, resolvedId);
        }
        return resolvedId;
      }

      if (storageKey) {
        sessionStorage.removeItem(storageKey);
      }
      return null;
    },
    enabled: !!documentId,
    staleTime: Infinity,
    retry: false,
  });

  const submitConfirmedPartial = useCallback(
    (program: string) => {
      if (!documentId || submitEvaluation.isPending) return;

      submitEvaluation
        .mutateAsync({
          document_id: documentId,
          partial_without_curriculum: true,
          confirmed_program: program,
        })
        .then((result) => {
          if (storageKey) {
            sessionStorage.setItem(storageKey, result.evaluation_id);
          }
          void queryClient.invalidateQueries({
            queryKey: ['resolve-evaluation', documentId],
          });
        })
        .catch(() => {
          // Error is surfaced by the mutation; the user can retry from setup.
        });
    },
    [documentId, submitEvaluation, storageKey, queryClient],
  );

  const handleRetrySubmit = useCallback(() => {
    submitEvaluation.reset();
  }, [submitEvaluation]);

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
      void queryClient.invalidateQueries({ queryKey: ['history'] });
      void queryClient.invalidateQueries({ queryKey: ['evaluations'] });
    }
  }, [status?.status, refetchResults, queryClient]);

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
    hasRecoveredRef.current = false;
    submitEvaluation.reset();
    void refetchResolve();
  }, [storageKey, refetchResolve, submitEvaluation]);

  const isSetupRequired = useMemo(() => {
    return !!documentId && !evaluationId && !isResolvingEval && !isLoadingDocument && !!document;
  }, [documentId, evaluationId, isResolvingEval, isLoadingDocument, document]);

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
    isLoadingDocument,
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
    // Setup
    isSetupRequired,
    effectiveProgram,
    detectedProgram,
    setSelectedProgram,
    submitConfirmedPartial,
  };
}
