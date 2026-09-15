import { useState, useMemo, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import { evaluationApi } from '../api/evaluation.api';
import { useSpecialistQueue } from './useSpecialistQueue';
import {
  isTargetAgent,
  TARGET_AGENT_META,
  type TargetAgent,
} from '@/shared/types/evaluations';
import type { ClientDocument } from '@/shared/types/documents';
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
  const [selectedDocId, setSelectedDocId] = useState<string | null>(routeDocId ?? null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);

  useEffect(() => {
    if (routeDocId) {
      setSelectedDocId(routeDocId);
    }
  }, [routeDocId]);

  // 1. Fetch specialist desk queue
  const {
    data: queueData,
    isLoading: isLoadingQueue,
    refetch: refetchQueue,
  } = useSpecialistQueue(validAgent);

  // 2. Fetch available processed SLMs from Storage to identify modules in storage
  const { data: docsData, isLoading: isLoadingDocs } = useQuery({
    queryKey: ['storage-slm-documents'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', page: 1, pageSize: 100 }),
    staleTime: 30000,
  });

  const slmDocuments: ClientDocument[] = useMemo(() => {
    return (docsData?.items ?? []).filter((d: ClientDocument) => d.processingStatus === 'PROCESSED');
  }, [docsData]);

  // Merge desk queue with storage SLMs
  const allQueueItems = useMemo<DeskQueueItem[]>(() => {
    if (queueData?.items && queueData.items.length > 0) {
      const queueDocIds = new Set(queueData.items.map((i) => i.document_id));
      const extraItems: DeskQueueItem[] = slmDocuments
        .filter((doc) => !queueDocIds.has(doc.documentId))
        .map((doc) => ({
          document_id: doc.documentId,
          title: doc.title,
          course_code: doc.courseCode ?? null,
          program: doc.program ?? null,
          uploaded_at: doc.uploadedAt ?? '',
          my_status: 'READY',
          my_score: null,
          my_adjectival: null,
          peer_completed_count: 0,
          peer_completed_desks: [],
        }));
      return [...queueData.items, ...extraItems];
    }
    if (slmDocuments.length > 0) {
      return slmDocuments.map((doc) => ({
        document_id: doc.documentId,
        title: doc.title,
        course_code: doc.courseCode ?? null,
        program: doc.program ?? null,
        uploaded_at: doc.uploadedAt ?? '',
        my_status: 'READY',
        my_score: null,
        my_adjectival: null,
        peer_completed_count: 0,
        peer_completed_desks: [],
      }));
    }
    return [];
  }, [queueData, slmDocuments]);

  // Filter queue to show pending files that need evaluation by this specialist
  const pendingItems = useMemo(() => {
    return allQueueItems.filter(
      (item) => (item.my_status || '').toUpperCase() !== 'COMPLETED',
    );
  }, [allQueueItems]);

  // Determine active document ID: selected > routeDocId > first pending > first item
  const activeDocId = useMemo(() => {
    if (selectedDocId) {
      const found = allQueueItems.find((item) => item.document_id === selectedDocId);
      if (found) return found.document_id;
    }
    if (routeDocId) {
      const found = allQueueItems.find((item) => item.document_id === routeDocId);
      if (found) return found.document_id;
    }
    const firstPending = allQueueItems.find(
      (item) => (item.my_status || '').toUpperCase() !== 'COMPLETED',
    );
    if (firstPending) return firstPending.document_id;
    return allQueueItems[0]?.document_id ?? null;
  }, [selectedDocId, routeDocId, allQueueItems]);

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

  const isCompleted =
    isJobCompleted || (activeItem?.my_status || '').toUpperCase() === 'COMPLETED';
  const isEvaluating =
    !isCompleted &&
    (isJobEvaluating || (activeItem?.my_status || '').toUpperCase() === 'EVALUATING');

  // Fetch completed evaluation results for the specialist desk
  const {
    data: results,
    isLoading: isLoadingResults,
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

  const handleDocumentChange = useCallback(
    (docId: string) => {
      void navigate({
        to: '/specialists/$agentId/$documentId',
        params: { agentId: validAgent, documentId: docId },
      });
    },
    [navigate, validAgent],
  );

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

  const isLoading = isLoadingDocs && isLoadingQueue;

  return {
    validAgent,
    meta,
    routeDocId,
    allQueueItems,
    pendingItems,
    activeItem,
    activeDocument,
    activeDocId,
    latestJob,
    latestJobId,
    isCompleted,
    isEvaluating,
    isLoading,
    isLoadingResults,
    results,
    domainScore,
    showConfirmModal,
    showReviewModal,
    setShowConfirmModal,
    setShowReviewModal,
    handleDocumentChange,
    handleModalSubmitted,
    handleReviewModalClose,
  };
}
