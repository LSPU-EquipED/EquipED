import { useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@equiped/api-client';
import type { DocumentUploadResponse } from '@equiped/types';
import { modelValidationApi } from '../api/modelValidation.api';
import { useModelValidationCriteria } from './useModelValidationQueries';
import { criterionKey, isPartialValidationAgent } from '../utils/helpers';

type CompareAgentId = 'sme' | 'gad' | 'itso';

export function useAdapterComparisonFormState() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<CompareAgentId | null>(null);
  const [expectedScores, setExpectedScores] = useState<Record<string, string>>({});
  const [uploaded, setUploaded] = useState<DocumentUploadResponse | null>(null);

  const criterionCatalog = useModelValidationCriteria();

  const uploadedDocument = useQuery({
    queryKey: ['documents', uploaded?.documentId],
    queryFn: () => documentsApi.getDocument(uploaded!.documentId),
    enabled: uploaded != null,
    refetchInterval: (query) => (query.state.data?.processingStatus === 'PENDING' ? 2000 : false),
  });

  const uploadMutation = useMutation({
    mutationFn: async (input: { file: File; title: string; program: string }) => {
      const document = await documentsApi.uploadDocument({ ...input, sourceType: 'slm' });
      if (document.processingStatus === 'FAILED') {
        throw new Error(
          document.errorMessage ??
            'SLM processing failed. Check that the PDF contains extractable text and try again.',
        );
      }
      return document;
    },
    onSuccess: (document) => setUploaded(document),
  });

  const compareMutation = useMutation({
    mutationFn: () => {
      if (!uploaded || !selectedAgent) {
        throw new Error('Select an agent and finish uploading the SLM first.');
      }
      const agentCatalog = criterionCatalog.data?.agents.find(
        (agent) => agent.agent_id === selectedAgent,
      );
      const criteria =
        agentCatalog?.domains && agentCatalog.domains.length > 0
          ? agentCatalog.domains.flatMap((d) => d.criteria)
          : agentCatalog?.criteria ?? [];
      return modelValidationApi.compareAdapter({
        document_id: uploaded.documentId,
        target_agent: selectedAgent,
        expected_scores: criteria.map((criterion) => ({
          agent_id: selectedAgent,
          rubric_set_id: agentCatalog!.rubric_set_id,
          rubric_criterion_id: criterion.rubric_criterion_id,
          expected_score: Number(
            expectedScores[
              criterionKey(selectedAgent, criterion.rubric_criterion_id || criterion.criterion_id!)
            ],
          ),
        })),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'model-validations'] });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'model-validation-metrics'] });
      setFile(null);
      setTitle('');
      setProgram('');
      setSelectedAgent(null);
      setExpectedScores({});
      setUploaded(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  const compareAgents = (criterionCatalog.data?.agents ?? []).filter((agent) =>
    isPartialValidationAgent(agent.agent_id),
  );
  const selectedAgentCatalog = compareAgents.find((agent) => agent.agent_id === selectedAgent);
  const selectedAgentCriteria = selectedAgentCatalog
    ? selectedAgentCatalog.domains && selectedAgentCatalog.domains.length > 0
      ? selectedAgentCatalog.domains.flatMap((d) => d.criteria)
      : selectedAgentCatalog.criteria
    : [];

  const allCriterionScoresComplete =
    selectedAgent != null &&
    selectedAgentCriteria.length > 0 &&
    selectedAgentCriteria.every((criterion) => {
      const key = criterionKey(
        selectedAgent,
        criterion.rubric_criterion_id || criterion.criterion_id!,
      );
      const score = Number(expectedScores[key]);
      return Number.isInteger(score) && score >= 1 && score <= 4;
    });

  const uploadedProcessingStatus =
    uploadedDocument.data?.processingStatus ?? uploaded?.processingStatus;
  const uploadedDocumentReady =
    uploadedProcessingStatus === 'PROCESSED' && (uploadedDocument.data?.chunks.length ?? 0) > 0;
  const canSubmitEvaluation = uploadedDocumentReady && allCriterionScoresComplete;
  const error = uploadMutation.error ?? uploadedDocument.error ?? compareMutation.error;

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploaded(null);
    if (nextFile && !title.trim()) setTitle(nextFile.name.replace(/\.pdf$/i, ''));
  };

  const handleProgramChange = (nextProgram: string) => setProgram(nextProgram.trim().toUpperCase());

  const handlePrepare = (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title.trim() || !program) return;
    uploadMutation.mutate({ file, title, program });
  };

  const handleStart = () => {
    if (!canSubmitEvaluation) return;
    compareMutation.mutate();
  };

  return {
    fileInputRef,
    file,
    title,
    setTitle,
    program,
    handleProgramChange,
    selectedAgent,
    setSelectedAgent,
    expectedScores,
    setExpectedScores,
    uploaded,
    criterionCatalog,
    compareAgents,
    selectedAgentCriteria,
    uploadMutation,
    compareMutation,
    allCriterionScoresComplete,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    canSubmitEvaluation,
    error,
    handleFile,
    handlePrepare,
    handleStart,
  };
}

export type AdapterComparisonFormState = ReturnType<typeof useAdapterComparisonFormState>;
