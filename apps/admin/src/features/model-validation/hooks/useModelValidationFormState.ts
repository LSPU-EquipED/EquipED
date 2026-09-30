import { useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@equiped/api-client';
import type { DocumentUploadResponse } from '@equiped/types';
import { modelValidationApi } from '../api/modelValidation.api';
import type { ModelChoice, ModelValidationCreateBody, TargetAgent } from '../types';
import {
  areAllCriterionScoresComplete,
  criterionKey,
  isPartialValidationAgent,
  isStaleBindingError,
} from '../utils/helpers';
import { useAdapterChoices, useModelValidationCriteria } from './useModelValidationQueries';

export function useModelValidationFormState() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scoreInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [expectedScores, setExpectedScores] = useState<Record<string, string>>({});
  const [uploaded, setUploaded] = useState<DocumentUploadResponse | null>(null);
  const [modelChoice, setModelChoice] = useState<ModelChoice>('base');
  const [targetAgent, setTargetAgentState] = useState<TargetAgent | null>(null);
  const adapterChoices = useAdapterChoices(targetAgent);

  const setTargetAgent = (next: TargetAgent) => {
    setTargetAgentState(next);
    setModelChoice('base'); // adapter versions belong to one agent
  };

  const criterionCatalog = useModelValidationCriteria();

  const uploadedDocument = useQuery({
    queryKey: ['documents', uploaded?.documentId],
    queryFn: () => documentsApi.getDocument(uploaded!.documentId),
    enabled: uploaded != null,
    refetchInterval: (query) => (query.state.data?.processingStatus === 'PENDING' ? 2000 : false),
  });

  const uploadMutation = useMutation({
    mutationFn: async (input: { file: File; title: string; program: string }) => {
      const document = await documentsApi.uploadDocument({
        ...input,
        sourceType: 'slm',
      });
      if (document.processingStatus === 'FAILED') {
        throw new Error(
          document.errorMessage ??
            'SLM processing failed. Check that the PDF contains extractable text and try again.',
        );
      }
      return document;
    },
    onSuccess: (document) => {
      setUploaded(document);
    },
  });

  const validationMutation = useMutation({
    mutationFn: async (body: ModelValidationCreateBody) => {
      const latestDocument = await documentsApi.getDocument(body.document_id);
      if (latestDocument.processingStatus === 'PENDING') {
        throw new Error(
          'The SLM is still being processed. Wait until it is ready, then try again.',
        );
      }
      if (latestDocument.processingStatus === 'FAILED') {
        throw new Error('SLM processing failed. Upload a valid PDF before starting validation.');
      }
      if (latestDocument.chunks.length === 0) {
        throw new Error(
          'SLM processing completed without stored text chunks. Upload the PDF again before validation.',
        );
      }
      return modelValidationApi.createModelValidation(body);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'model-validations'] });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'model-validation-metrics'] });
      setFile(null);
      setTitle('');
      setProgram('');
      setExpectedScores({});
      setUploaded(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  const rawAgents = criterionCatalog.data?.agents ?? [];
  const partialAgentDefinitions = rawAgents.filter((agent) =>
    isPartialValidationAgent(agent.agent_id),
  );
  const criterionDefinitions = targetAgent
    ? partialAgentDefinitions.filter((agent) => agent.agent_id === targetAgent)
    : [];

  const adapters = adapterChoices.data?.adapters ?? [];
  const published = adapters.find((a) => a.published) ?? null;
  const adapterOptions = [
    { value: 'base', label: 'Base model (no adapter)', disabled: false },
    ...(published
      ? [
          {
            value: 'published',
            label: `Published (v${published.version})`,
            disabled: published.loaded !== true,
          },
        ]
      : []),
    ...adapters.map((a) => ({
      value: a.adapter_id,
      label: `v${a.version}${a.published ? ' ★ published' : ''}${
        a.loaded === true
          ? ' · loaded'
          : a.loaded === false
            ? ' · not loaded'
            : ' · unknown'
      }`,
      disabled: a.loaded !== true,
    })),
  ];
  const chosenAdapter =
    modelChoice === 'base'
      ? null
      : modelChoice === 'published'
        ? published
        : (adapters.find((a) => a.adapter_id === modelChoice) ?? null);
  const modelChoiceValid = modelChoice === 'base' || chosenAdapter?.loaded === true;

  const orderedCriterionKeys = criterionDefinitions.flatMap((agent) => {
    const crits =
      agent.domains && agent.domains.length > 0
        ? agent.domains.flatMap((d) => d.criteria)
        : agent.criteria;
    return crits.map((criterion) =>
      criterionKey(agent.agent_id, criterion.rubric_criterion_id || criterion.criterion_id!),
    );
  });

  // Validity derives from the active criterion catalog (SME/GAD/ITSO for
  // explicit no-curriculum partial runs), not a fixed agent count.
  const allCriterionScoresComplete = areAllCriterionScoresComplete(
    criterionDefinitions,
    expectedScores,
  );
  const uploadedProcessingStatus =
    uploadedDocument.data?.processingStatus ?? uploaded?.processingStatus;
  const uploadedDocumentReady =
    uploadedProcessingStatus === 'PROCESSED' && (uploadedDocument.data?.chunks.length ?? 0) > 0;
  const canSubmitEvaluation =
    uploadedDocumentReady && allCriterionScoresComplete && targetAgent != null && modelChoiceValid;
  const error = uploadMutation.error ?? uploadedDocument.error ?? validationMutation.error;
  const isStaleBinding = isStaleBindingError(validationMutation.error);

  const handleReloadCatalog = async () => {
    validationMutation.reset();
    await criterionCatalog.refetch();
  };

  const resetPreparedUpload = () => {
    setFile(null);
    setUploaded(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploaded(null);
    if (nextFile && !title.trim()) setTitle(nextFile.name.replace(/\.pdf$/i, ''));
  };

  const handleProgramChange = (nextProgram: string) => {
    const normalized = nextProgram.trim().toUpperCase();
    setProgram(normalized);
  };

  const handlePrepare = (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title.trim() || !program || !allCriterionScoresComplete) return;
    uploadMutation.mutate({ file, title, program });
  };

  const registerScoreInput = (key: string, node: HTMLInputElement | null) => {
    if (node) scoreInputRefs.current[key] = node;
    else delete scoreInputRefs.current[key];
  };

  const handleScoreKeyDown = (event: KeyboardEvent<HTMLInputElement>, currentKey: string) => {
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault();
      return;
    }

    if (event.key !== 'Enter') {
      const isPrintableKey = event.key.length === 1;
      const isEditingShortcut = event.ctrlKey || event.metaKey || event.altKey;
      if (isPrintableKey && !isEditingShortcut && !/^[1-4]$/.test(event.key)) {
        event.preventDefault();
      }
      return;
    }

    event.preventDefault();
    const currentIndex = orderedCriterionKeys.indexOf(currentKey);
    const nextKey = orderedCriterionKeys[currentIndex + 1];
    if (nextKey) {
      scoreInputRefs.current[nextKey]?.focus();
      scoreInputRefs.current[nextKey]?.select();
    }
  };

  const handleStart = () => {
    if (!uploaded || !canSubmitEvaluation) return;
    validationMutation.mutate({
      document_id: uploaded.documentId,
      partial_without_curriculum: false,
      target_agent: targetAgent!,
      model_variant: chosenAdapter ? 'adapter' : 'base',
      ...(chosenAdapter ? { adapter_id: chosenAdapter.adapter_id } : {}),
      expected_scores: criterionDefinitions.flatMap((agent) => {
        const crits =
          agent.domains && agent.domains.length > 0
            ? agent.domains.flatMap((d) => d.criteria)
            : agent.criteria;
        return crits.map((criterion) => ({
          agent_id: agent.agent_id as 'sme' | 'gad' | 'itso',
          rubric_set_id: agent.rubric_set_id,
          rubric_criterion_id: criterion.rubric_criterion_id,
          expected_score: Number(
            expectedScores[
              criterionKey(agent.agent_id, criterion.rubric_criterion_id || criterion.criterion_id!)
            ],
          ),
        }));
      }),
    });
  };

  return {
    fileInputRef,
    registerScoreInput,
    file,
    title,
    setTitle,
    program,
    expectedScores,
    setExpectedScores,
    uploaded,
    modelChoice,
    setModelChoice,
    adapterOptions,
    adapterChoices,
    targetAgent,
    setTargetAgent,
    criterionCatalog,
    uploadMutation,
    validationMutation,
    criterionDefinitions,
    allCriterionScoresComplete,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    canSubmitEvaluation,
    error,
    isStaleBinding,
    handleReloadCatalog,
    resetPreparedUpload,
    handleFile,
    handleProgramChange,
    handlePrepare,
    handleScoreKeyDown,
    handleStart,
  };
}

export type ModelValidationFormState = ReturnType<typeof useModelValidationFormState>;
