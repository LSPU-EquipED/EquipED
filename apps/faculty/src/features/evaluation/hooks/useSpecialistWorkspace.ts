import { useState, useMemo, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@equiped/api-client';
import { evaluationApi } from '../api/evaluation.api';
import { useSpecialistQueue } from './useSpecialistQueue';
import {
  isTargetAgent,
  TARGET_AGENT_META,
  type TargetAgent,
} from '@equiped/types';
import type { ClientDocument } from '@equiped/types';
import type { DeskQueueItem, DomainScoreBlock } from '../types';

export interface UseSpecialistWorkspaceOptions {
  agentId?: TargetAgent;
  documentId?: string;
}

export function useSpecialistWorkspace({
  agentId: propAgentId,
  documentId: propDocId,
}: UseSpecialistWorkspaceOptions = {}) {
  const params = useParams({ strict: false }) as {
    agentId?: string;
    documentId?: string;
  };
  const resolvedAgent = propAgentId ?? params.agentId;
  const validAgent: TargetAgent = isTargetAgent(resolvedAgent) ? resolvedAgent : 'sme';
  const meta = TARGET_AGENT_META[validAgent];
  const routeDocId = propDocId ?? params.documentId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);

  // 1. Fetch specialist desk queue
  // When routeDocId is provided, fetch authoritative desk status via documentId option;
  // otherwise fetch the full queue for this agent.
  const {
    data: queueData,
    isLoading: isLoadingQueue,
    refetch: refetchQueue,
  } = useSpecialistQueue(
    validAgent,
    undefined,
    routeDocId ? { documentId: routeDocId } : undefined,
  );

  // 2. Fetch available processed SLMs from Storage to identify modules in storage
  const { data: docsData, isLoading: isLoadingDocs } = useQuery({
    queryKey: ['storage-slm-documents'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', page: 1, pageSize: 100 }),
    staleTime: 30000,
  });

  // 3. If routeDocId is provided, fetch exact document through ownership-scoped getDocument
  const {
    data: exactDocData,
    isLoading: isLoadingExactDoc,
    isError: _isExactDocError,
  } = useQuery({
    queryKey: ['storage-document', routeDocId],
    queryFn: () => documentsApi.getDocument(routeDocId!),
    enabled: Boolean(routeDocId),
    staleTime: 30000,
    retry: false,
  });

  const targetedDoc: ClientDocument | null = useMemo(() => {
    if (!routeDocId || !exactDocData) return null;
    if (exactDocData.sourceType === 'slm' && exactDocData.processingStatus === 'PROCESSED') {
      return exactDocData;
    }
    return null;
  }, [routeDocId, exactDocData]);

  const slmDocuments: ClientDocument[] = useMemo(() => {
    const list = (docsData?.items ?? []).filter((d: ClientDocument) => d.processingStatus === 'PROCESSED');
    if (targetedDoc && !list.some((doc) => doc.documentId === targetedDoc.documentId)) {
      return [targetedDoc, ...list];
    }
    return list;
  }, [docsData, targetedDoc]);

  // Desk queue items from the server are the authoritative source of truth.
  // Do NOT synthesize READY status for storage documents that are missing from desk queue!
  const allQueueItems = useMemo<DeskQueueItem[]>(() => {
    return queueData?.items ?? [];
  }, [queueData]);

  // A targeted route must resolve to an owned queue item; never substitute another module.
  const activeDocId = useMemo(() => {
    if (routeDocId) {
      return allQueueItems.find((item) => item.document_id === routeDocId)?.document_id ?? null;
    }
    const firstPending = allQueueItems.find(
      (item) => (item.my_status || '').toUpperCase() !== 'COMPLETED',
    );
    if (firstPending) return firstPending.document_id;
    return allQueueItems[0]?.document_id ?? null;
  }, [routeDocId, allQueueItems]);

  useEffect(() => {
    if (!routeDocId) return;
    if (isLoadingDocs || isLoadingQueue || isLoadingExactDoc) return;

    // If routeDocId is provided and the desk returns no item for that document, redirect to /specialists/$agentId
    const isPresentInQueue = allQueueItems.some((item) => item.document_id === routeDocId);
    if (!isPresentInQueue) {
      void navigate({ to: '/specialists/$agentId', params: { agentId: validAgent } });
    }
  }, [
    routeDocId,
    allQueueItems,
    isLoadingDocs,
    isLoadingQueue,
    isLoadingExactDoc,
    navigate,
    validAgent,
  ]);

  const activeItem = useMemo(() => {
    if (!activeDocId) return null;
    return allQueueItems.find((item) => item.document_id === activeDocId) ?? null;
  }, [allQueueItems, activeDocId]);

  const activeDocument = useMemo(() => {
    if (!activeDocId) return null;
    return slmDocuments.find((doc) => doc.documentId === activeDocId) ?? null;
  }, [slmDocuments, activeDocId]);

  // 4. Resolve the latest evaluation job for this SLM and this specialist role
  const { data: evalsData, refetch: refetchEvals } = useQuery({
    queryKey: ['specialist-evaluations', activeDocId, validAgent],
    queryFn: () => evaluationApi.listEvaluations(activeDocId!, validAgent),
    enabled: Boolean(activeDocId),
    staleTime: 5000,
    refetchInterval: (query) => {
      const latest = query.state.data?.items?.find(
        (job) => job.target_agent === validAgent,
      );
      const isEvaluating =
        latest?.status === 'SUBMITTED' ||
        latest?.status === 'PREPROCESSING' ||
        latest?.status === 'EVALUATING' ||
        latest?.status === 'SYNTHESIZING';
      return isEvaluating ? 2000 : false;
    },
  });

  const latestJob = useMemo(() => {
    if (!evalsData?.items) return null;
    return evalsData.items.find((job) => job.target_agent === validAgent) ?? null;
  }, [evalsData, validAgent]);
  const latestJobId = latestJob?.evaluation_id;
  const isJobEvaluating =
    latestJob?.status === 'SUBMITTED' ||
    latestJob?.status === 'PREPROCESSING' ||
    latestJob?.status === 'EVALUATING' ||
    latestJob?.status === 'SYNTHESIZING';
  const isJobCompleted = latestJob?.status === 'COMPLETED';

  const isCompleted = Boolean(latestJobId && isJobCompleted);
  const isEvaluating =
    !isCompleted &&
    (isJobEvaluating || (activeItem?.my_status || '').toUpperCase() === 'EVALUATING');

  // Fetch completed evaluation results for the specialist desk
  const {
    data: results,
    isLoading: isLoadingResults,
    isError: isResultsError,
    refetch: refetchResults,
  } = useQuery({
    queryKey: ['specialist-results', latestJobId],
    queryFn: () => evaluationApi.getEvaluationResults(latestJobId!),
    enabled: Boolean(latestJobId && isCompleted),
    staleTime: 30000,
  });

  const domainScore: DomainScoreBlock | undefined = useMemo(() => {
    if (!results?.domain_scores) return undefined;
    return (
      results.domain_scores[validAgent] ||
      results.domain_scores[validAgent.toLowerCase()]
    );
  }, [results, validAgent]);

  const handleReviewModalClose = useCallback(() => {
    setShowReviewModal(false);
    void queryClient.invalidateQueries({ queryKey: ['specialist-results'] });
    void queryClient.invalidateQueries({ queryKey: ['specialist-evaluations'] });
    void queryClient.invalidateQueries({ queryKey: ['specialist-queue'] });
    void queryClient.invalidateQueries({ queryKey: ['evaluation-results'] });
    void refetchResults();
    void refetchQueue();
  }, [queryClient, refetchResults, refetchQueue]);

  const handleModalSubmitted = useCallback(
    (_newEvalId?: string) => {
      setShowConfirmModal(false);
      void queryClient.invalidateQueries({ queryKey: ['specialist-queue'] });
      void queryClient.invalidateQueries({ queryKey: ['specialist-evaluations'] });
      void queryClient.invalidateQueries({ queryKey: ['specialist-results'] });
      void refetchQueue();
      void refetchEvals();
      if (activeDocId) {
        void navigate({
          to: '/specialists/$agentId/$documentId',
          params: { agentId: validAgent, documentId: activeDocId },
        });
      }
    },
    [queryClient, refetchQueue, refetchEvals, activeDocId, validAgent, navigate],
  );

  const isLoading = isLoadingDocs || isLoadingQueue || (Boolean(routeDocId) && isLoadingExactDoc);

  return {
    validAgent,
    meta,
    routeDocId,
    allQueueItems,
    activeItem,
    activeDocument,
    activeDocId,
    latestJob,
    latestJobId,
    isCompleted,
    isEvaluating,
    isLoading,
    isLoadingResults,
    isResultsError,
    refetchResults,
    results,
    domainScore,
    showConfirmModal,
    showReviewModal,
    setShowConfirmModal,
    setShowReviewModal,
    handleModalSubmitted,
    handleReviewModalClose,
  };
}
