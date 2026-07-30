import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import type {
  CurriculumSuggestionResponse,
  DocumentUploadResponse,
} from '@/shared/types/documents';
import { modelValidationApi } from '../api/modelValidation.api';
import type { ModelValidationCreateBody } from '../types';
import { criterionKey } from '../utils/helpers';
import { useModelValidationCriteria } from './useModelValidationQueries';

export function useModelValidationFormState() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scoreInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const persistedProgramRef = useRef<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [expectedScores, setExpectedScores] = useState<Record<string, string>>({});
  const [uploaded, setUploaded] = useState<DocumentUploadResponse | null>(null);
  const [curriculumId, setCurriculumId] = useState('');
  const [allowPartial, setAllowPartial] = useState(false);
  const [partialChoiceAcknowledged, setPartialChoiceAcknowledged] = useState(false);

  const criterionCatalog = useModelValidationCriteria();

  const uploadedDocument = useQuery({
    queryKey: ['documents', uploaded?.documentId],
    queryFn: () => documentsApi.getDocument(uploaded!.documentId),
    enabled: uploaded != null,
    refetchInterval: (query) => (query.state.data?.processingStatus === 'PENDING' ? 2000 : false),
  });

  const normalizedProgram = program.trim().toUpperCase();
  const suggestionsQuery = useQuery<CurriculumSuggestionResponse>({
    queryKey: [
      'model-validation',
      'curriculum-suggestion',
      uploaded?.documentId,
      normalizedProgram,
    ],
    queryFn: () => {
      if (!uploaded) {
        throw new Error('No uploaded document');
      }
      return documentsApi.getCurriculumSuggestion(uploaded.documentId, normalizedProgram);
    },
    enabled: !!uploaded && normalizedProgram.length > 0,
    retry: 1,
  });
  const suggestions = suggestionsQuery.data ?? null;

  useEffect(() => {
    if (uploaded && suggestions && !suggestionsQuery.isFetching) {
      persistedProgramRef.current = normalizedProgram;
    }
  }, [uploaded, suggestions, normalizedProgram, suggestionsQuery.isFetching]);

  useEffect(() => {
    if (!uploaded) return;
    if (!persistedProgramRef.current) return;
    if (normalizedProgram === persistedProgramRef.current) return;
    setCurriculumId('');
  }, [uploaded, normalizedProgram]);

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
      setCurriculumId('');
      setAllowPartial(false);
      setPartialChoiceAcknowledged(false);
      persistedProgramRef.current = '';
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
      setCurriculumId('');
      setAllowPartial(false);
      setPartialChoiceAcknowledged(false);
      persistedProgramRef.current = '';
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  const criterionDefinitions = criterionCatalog.data?.agents ?? [];
  const orderedCriterionKeys = criterionDefinitions.flatMap((agent) =>
    agent.criteria.map((criterion) => criterionKey(agent.agent_id, criterion.criterion_id)),
  );
  const allCriterionScoresComplete =
    criterionDefinitions.length === 4 &&
    (criterionCatalog.data?.total_criteria ?? 0) > 0 &&
    criterionDefinitions.every((agent) =>
      agent.criteria.every((criterion) => {
        const score = Number(expectedScores[criterionKey(agent.agent_id, criterion.criterion_id)]);
        return Number.isInteger(score) && score >= 1 && score <= 4;
      }),
    );
  const readyCurricula = suggestions?.curriculumSuggestions ?? [];
  const unavailableCurricula = suggestions?.unavailableCurricula ?? [];
  const uploadedProcessingStatus =
    uploadedDocument.data?.processingStatus ?? uploaded?.processingStatus;
  const uploadedDocumentReady =
    uploadedProcessingStatus === 'PROCESSED' && (uploadedDocument.data?.chunks.length ?? 0) > 0;
  const isSuggestionsLoading = suggestionsQuery.isLoading || suggestionsQuery.isFetching;
  const isSuggestionsError = suggestionsQuery.isError;
  const showPartialOption = uploadedDocumentReady && readyCurricula.length === 0;
  const canSubmitEvaluation =
    uploadedDocumentReady &&
    allCriterionScoresComplete &&
    (!!curriculumId || (allowPartial && partialChoiceAcknowledged && readyCurricula.length === 0));
  const error = uploadMutation.error ?? uploadedDocument.error ?? validationMutation.error;

  const resetPreparedUpload = () => {
    setFile(null);
    setUploaded(null);
    setCurriculumId('');
    setAllowPartial(false);
    setPartialChoiceAcknowledged(false);
    persistedProgramRef.current = '';
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploaded(null);
    setCurriculumId('');
    if (nextFile && !title.trim()) setTitle(nextFile.name.replace(/\.pdf$/i, ''));
  };

  const handleProgramChange = (nextProgram: string) => {
    const normalized = nextProgram.trim().toUpperCase();
    setProgram(normalized);
    if (uploaded) {
      setCurriculumId('');
    }
  };

  const handlePrepare = (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title.trim() || !program || !allCriterionScoresComplete) return;
    uploadMutation.mutate({ file, title, program });
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
      curriculum_id: curriculumId || undefined,
      partial_without_curriculum: !curriculumId && allowPartial && partialChoiceAcknowledged,
      expected_scores: criterionDefinitions.flatMap((agent) =>
        agent.criteria.map((criterion) => ({
          agent_id: agent.agent_id,
          criterion_id: criterion.criterion_id,
          expected_score: Number(
            expectedScores[criterionKey(agent.agent_id, criterion.criterion_id)],
          ),
        })),
      ),
    });
  };

  return {
    fileInputRef,
    scoreInputRefs,
    file,
    title,
    setTitle,
    program,
    expectedScores,
    setExpectedScores,
    uploaded,
    curriculumId,
    setCurriculumId,
    allowPartial,
    setAllowPartial,
    partialChoiceAcknowledged,
    setPartialChoiceAcknowledged,
    criterionCatalog,
    uploadMutation,
    validationMutation,
    criterionDefinitions,
    allCriterionScoresComplete,
    readyCurricula,
    unavailableCurricula,
    uploadedProcessingStatus,
    uploadedDocumentReady,
    isSuggestionsLoading,
    isSuggestionsError,
    showPartialOption,
    canSubmitEvaluation,
    error,
    normalizedProgram,
    resetPreparedUpload,
    handleFile,
    handleProgramChange,
    handlePrepare,
    handleScoreKeyDown,
    handleStart,
  };
}
