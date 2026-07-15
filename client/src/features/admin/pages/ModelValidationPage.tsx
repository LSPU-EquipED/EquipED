import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Link } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  FileCheck2,
  Loader2,
  Play,
  ShieldAlert,
  Upload,
} from 'lucide-react';
import { documentsApi } from '@/shared/api/documents.api';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { cn } from '@/shared/components/utils';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import type {
  CurriculumSuggestionResponse,
  DocumentUploadResponse,
} from '@/shared/types/documents';
import { adminApi } from '../api/admin.api';
import type {
  AdminEvaluationResponse,
  ModelValidationCreateBody,
  ModelValidationCriterionScore,
  ModelValidationItem,
} from '../types';
import {
  calculateConfusionMatrixMetrics,
  emptyConfusionMatrix,
  hasConfusionMatrixData,
} from '../utils/confusionMatrix';

const terminalStatuses = new Set(['COMPLETED', 'FAILED']);
const criterionKey = (agentId: string, criterionId: string) => `${agentId}:${criterionId}`;
const validationAgents = [
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'gad', label: 'GAD Evaluator' },
  { id: 'itso', label: 'IT Security Officer' },
] as const;
const agentLabel = (id: string) =>
  validationAgents.find((agent) => agent.id === id)?.label ?? id.toUpperCase();
const HISTORY_COLSPAN = 10;

function statusClass(status: ModelValidationItem['status']) {
  if (status === 'COMPLETED') return 'bg-[#3b963e] text-white';
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  if (status === 'EVALUATING' || status === 'SYNTHESIZING') return 'bg-[#1b3b87] text-white';
  return 'bg-[#f2c811] text-slate-900';
}

export function ModelValidationPage() {
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
  // Partial validation requires an explicit opt-in. Default false so the
  // checkbox is never pre-ticked — Coordinator curriculum-grounded review
  // is only skipped when the admin actively consents.
  const [allowPartial, setAllowPartial] = useState(false);
  // Preserves the admin's explicit partial choice across program changes.
  const [partialChoiceAcknowledged, setPartialChoiceAcknowledged] = useState(false);
  const [expandedValidationId, setExpandedValidationId] = useState<string | null>(null);

  const history = useQuery({
    queryKey: ['admin', 'model-validations'],
    queryFn: adminApi.getModelValidations,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => !terminalStatuses.has(item.status)) ? 3000 : false,
  });
  const criterionCatalog = useQuery({
    queryKey: ['admin', 'model-validation-criteria'],
    queryFn: adminApi.getModelValidationCriteria,
  });
  const metricSummary = useQuery({
    queryKey: ['admin', 'model-validation-metrics'],
    queryFn: adminApi.getModelValidationMetrics,
    refetchInterval: history.data?.items.some((item) => !terminalStatuses.has(item.status))
      ? 3000
      : false,
  });
  const uploadedDocument = useQuery({
    queryKey: ['documents', uploaded?.documentId],
    queryFn: () => documentsApi.getDocument(uploaded!.documentId),
    enabled: uploaded != null,
    refetchInterval: (query) => (query.state.data?.processingStatus === 'PENDING' ? 2000 : false),
  });

  // Curriculum suggestions become a useQuery keyed on the current program so
  // that editing the program (after the SLM is uploaded) automatically
  // refetches the suggestions for the new program. Any previously chosen
  // curriculum is cleared to prevent submitting a stale curriculum whose
  // program no longer matches the SLM. The user's explicit partial opt-in
  // is preserved across program changes — only the curriculum selection
  // is invalidated, not the partial intent.
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

  // Mark the current program as persisted when suggestions are fresh for
  // that program. Wait until the query is no longer fetching so we do not
  // stamp the new program while the previous program's data is still in
  // the cache.
  useEffect(() => {
    if (uploaded && suggestions && !suggestionsQuery.isFetching) {
      persistedProgramRef.current = normalizedProgram;
    }
  }, [uploaded, suggestions, normalizedProgram, suggestionsQuery.isFetching]);

  // When the selected program changes after a document is uploaded, clear
  // the stale curriculum selection. The partial opt-in (and any explicit
  // acknowledgement) is preserved across program changes.
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
      return adminApi.createModelValidation(body);
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
  // Submission is allowed only when a ready curriculum is selected, or when
  // the admin has explicitly opted into the partial/no-curriculum path and
  // acknowledged that Coordinator will be skipped.
  const canSubmitEvaluation =
    uploadedDocumentReady &&
    allCriterionScoresComplete &&
    (!!curriculumId || (allowPartial && partialChoiceAcknowledged && readyCurricula.length === 0));
  const error = uploadMutation.error ?? uploadedDocument.error ?? validationMutation.error;
  const activeValidations =
    history.data?.items.filter((item) => !terminalStatuses.has(item.status)) ?? [];

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

  return (
    <section className="grid min-w-0 gap-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Model Validation</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          Run the standard multi-agent SLM evaluation against an independent human benchmark.
          Expected scores are entered for every active agent criterion, stay private from the
          evaluator agents, and use the institutional 1–4 scale.
        </p>
      </header>

      <section
        aria-labelledby="validation-performance-heading"
        className="grid gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]"
      >
        <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h2
              id="validation-performance-heading"
              className="text-xs font-bold uppercase tracking-wider text-slate-700"
            >
              Performance metrics
            </h2>
          </div>
          <dl className="divide-y divide-slate-200">
            <MetricRow
              label="Completed runs"
              value={String(metricSummary.data?.completed_runs ?? 0)}
            />
            <MetricRow
              label="Mean absolute error"
              value={metricSummary.data?.mean_absolute_error?.toFixed(2) ?? '—'}
            />
            <MetricRow
              label="Mean latency"
              value={
                metricSummary.data?.mean_latency_seconds == null
                  ? '—'
                  : `${metricSummary.data.mean_latency_seconds.toFixed(2)} s`
              }
            />
            <MetricRow
              label="Score perplexity"
              value={metricSummary.data?.score_perplexity?.toFixed(2) ?? '—'}
            />
            <MetricRow
              label="Mean toxicity"
              value={
                metricSummary.data?.mean_toxicity_score == null
                  ? '—'
                  : `${(metricSummary.data.mean_toxicity_score * 100).toFixed(2)}%`
              }
            />
          </dl>
          <div className="grid gap-2 border-t border-slate-200 p-4 text-xs leading-relaxed text-slate-600">
            <p>
              Toxicity reads stored agent summaries and criterion justifications. Model Validation
              stores the resulting assessment and model provenance, not a duplicate comment.
            </p>
            <p>Automated evaluations remain advisory. Human review is authoritative.</p>
          </div>
        </div>

        <ConfusionMatrix
          labels={metricSummary.data?.class_labels ?? ['1', '2', '3', '4']}
          matrix={
            metricSummary.data?.confusion_matrix ?? [
              [0, 0, 0, 0],
              [0, 0, 0, 0],
              [0, 0, 0, 0],
              [0, 0, 0, 0],
            ]
          }
          agentMatrices={metricSummary.data?.agent_confusion_matrices}
          isLoading={metricSummary.isLoading}
          isError={metricSummary.isError}
        />
      </section>

      <details className="group overflow-hidden rounded-sm border border-slate-200 bg-white">
        <summary className="flex cursor-pointer list-none items-center gap-3 bg-slate-50 px-5 py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1b3b87] [&::-webkit-details-marker]:hidden">
          <span className="min-w-0">
            <span className="block text-sm font-bold uppercase tracking-wider text-slate-800">
              New validation input
            </span>
            <span className="mt-1 block text-xs font-medium normal-case tracking-normal text-slate-600">
              Upload an SLM and enter the human benchmark for each active agent criterion.
            </span>
          </span>
          <span className="ml-auto hidden text-xs font-bold uppercase tracking-wider text-[#1b3b87] sm:block">
            Expand
          </span>
          <ChevronDown
            className="size-5 shrink-0 text-[#1b3b87] transition-transform group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>
        <form onSubmit={handlePrepare} className="grid min-w-0 gap-5 border-t border-slate-200 p-5">
          <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
            SLM title
            <input
              className="h-10 min-w-0 w-full rounded-sm border border-slate-200 px-3 text-sm font-semibold normal-case tracking-normal focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              disabled={!!uploaded}
            />
          </label>

          <ProgramSelector
            id="validation-program"
            label="Confirmed program"
            value={program}
            onChange={handleProgramChange}
            groups={LSPU_SCC_COLLEGE_PROGRAMS}
            placeholder="Select the SLM program"
            required
            hint="Used to find the matching indexed curriculum."
          />

          <div className="grid min-w-0 gap-4 border-t border-slate-200 pt-5">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                Expected criterion scores
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                Enter the authoritative human score for every criterion before running the model.
              </p>
            </div>
            {criterionCatalog.isLoading ? (
              <p className="text-sm font-semibold text-slate-600">Loading active criteria…</p>
            ) : criterionCatalog.isError ? (
              <p className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-3 text-sm font-semibold text-[#b91c1c]">
                Unable to load the active rubric criteria.
              </p>
            ) : criterionDefinitions.length !== 4 ||
              criterionDefinitions.some((agent) => agent.criteria.length === 0) ? (
              <p className="rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-3 text-sm font-semibold text-slate-800">
                No active rubric criteria are available. Activate all four agent rubrics first.
              </p>
            ) : (
              criterionDefinitions.map((agent) => (
                <section
                  key={agent.agent_id}
                  className="overflow-hidden rounded-sm border border-slate-200"
                >
                  <div className="flex min-w-0 items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
                    <h3 className="min-w-0 break-words text-sm font-bold text-slate-900">
                      {agent.agent_name}
                    </h3>
                    <span className="shrink-0 text-xs font-semibold text-slate-600">
                      Rubric v{agent.rubric_version}
                    </span>
                  </div>
                  <div className="divide-y divide-slate-200">
                    {agent.criteria.map((criterion) => {
                      const key = criterionKey(agent.agent_id, criterion.criterion_id);
                      return (
                        <label
                          key={key}
                          className="grid min-w-0 gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center"
                        >
                          <span className="min-w-0">
                            <span className="block break-words text-sm font-semibold text-slate-900">
                              {criterion.criterion_id} · {criterion.title}
                            </span>
                            <span className="mt-0.5 block break-words text-xs leading-relaxed text-slate-600">
                              {criterion.domain_title} — {criterion.description}
                            </span>
                          </span>
                          <span className="grid min-w-0 gap-1 text-xs font-bold uppercase tracking-wider text-slate-600">
                            Score
                            <input
                              ref={(node) => {
                                scoreInputRefs.current[key] = node;
                              }}
                              type="text"
                              inputMode="numeric"
                              pattern="[1-4]"
                              maxLength={1}
                              autoComplete="off"
                              placeholder="1–4"
                              value={expectedScores[key] ?? ''}
                              onChange={(event) => {
                                const nextScore = event.target.value;
                                if (!/^[1-4]?$/.test(nextScore)) return;
                                setExpectedScores((current) => ({
                                  ...current,
                                  [key]: nextScore,
                                }));
                              }}
                              onKeyDown={(event) => handleScoreKeyDown(event, key)}
                              onFocus={(event) => event.currentTarget.select()}
                              className="h-10 min-w-0 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                              required
                            />
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </section>
              ))
            )}
          </div>

          <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center focus-within:ring-2 focus-within:ring-[#1b3b87]">
            <Upload className="size-6 text-[#1b3b87]" aria-hidden="true" />
            <span className="text-sm font-semibold text-slate-800">
              {file?.name ?? 'Choose an SLM PDF'}
            </span>
            <span className="text-xs font-medium text-slate-600">
              The file is stored locally and evaluated as direct input.
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="sr-only"
              onChange={handleFile}
              disabled={!!uploaded}
              required={!uploaded}
            />
          </label>

          {!uploaded ? (
            <button
              type="submit"
              disabled={
                !file ||
                !title.trim() ||
                !program ||
                !allCriterionScoresComplete ||
                uploadMutation.isPending
              }
              className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            >
              {uploadMutation.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileCheck2 className="size-4" />
              )}
              {uploadMutation.isPending ? 'Preparing SLM…' : 'Prepare validation'}
            </button>
          ) : (
            <div className="grid gap-4 border-t border-slate-200 pt-5">
              {uploadedDocumentReady ? (
                <div className="flex items-center gap-2 text-sm font-semibold text-[#3b963e]">
                  <CheckCircle className="size-5" />
                  SLM processed and ready
                </div>
              ) : uploadedProcessingStatus === 'FAILED' ? (
                <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-[#b91c1c]">
                  <span>SLM processing failed. Upload the PDF again before validation.</span>
                  <button
                    type="button"
                    onClick={resetPreparedUpload}
                    className="rounded-sm border border-[#b91c1c]/40 bg-white px-3 py-2 text-xs font-bold uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-[#b91c1c]"
                  >
                    Choose another PDF
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <Loader2 className="size-5 animate-spin text-[#1b3b87]" />
                  Confirming the SLM is fully processed…
                </div>
              )}
              {uploadedDocumentReady && isSuggestionsLoading ? (
                <div
                  role="status"
                  className="flex items-center gap-2 rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600"
                >
                  <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
                  Loading curriculum suggestions for {normalizedProgram}…
                </div>
              ) : null}
              {uploadedDocumentReady && isSuggestionsError ? (
                <p
                  role="alert"
                  className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-3 text-sm font-semibold text-[#b91c1c]"
                >
                  Unable to load curriculum suggestions for {normalizedProgram}. Try a different
                  program or retry the upload.
                </p>
              ) : null}
              {uploadedDocumentReady &&
              !isSuggestionsLoading &&
              !isSuggestionsError &&
              readyCurricula.length ? (
                <label className="grid gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                  Curriculum reference
                  <select
                    value={curriculumId}
                    onChange={(event) => setCurriculumId(event.target.value)}
                    className="h-10 min-w-0 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-semibold normal-case tracking-normal focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                  >
                    {readyCurricula.map((item) => (
                      <option key={item.documentId} value={item.documentId}>
                        {item.title}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {uploadedDocumentReady &&
              !isSuggestionsLoading &&
              !isSuggestionsError &&
              unavailableCurricula.length > 0 ? (
                <div className="rounded-sm border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
                  <p className="font-semibold text-slate-800">
                    Unavailable curricula for {normalizedProgram}
                  </p>
                  <p className="mt-1">
                    {unavailableCurricula.length} reference
                    {unavailableCurricula.length === 1 ? '' : 's'} not ready for retrieval. Ask an
                    admin to rebuild or re-upload them before full evaluation.
                  </p>
                </div>
              ) : null}
              {showPartialOption && !isSuggestionsLoading && !isSuggestionsError ? (
                <fieldset className="grid gap-3 rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-4 text-sm text-slate-900">
                  <legend className="px-1 text-xs font-bold uppercase tracking-wider text-slate-800">
                    Partial validation opt-in
                  </legend>
                  <label className="flex items-start gap-3 font-semibold text-slate-900">
                    <input
                      type="checkbox"
                      checked={allowPartial}
                      onChange={(event) => {
                        setAllowPartial(event.target.checked);
                        if (!event.target.checked) {
                          setPartialChoiceAcknowledged(false);
                        }
                      }}
                      className="mt-1 size-4 shrink-0 accent-[#1b3b87]"
                    />
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-slate-900">
                        Continue with a partial validation.
                      </span>
                      <span className="mt-1 block text-xs font-medium leading-relaxed text-slate-700">
                        No indexed curriculum is available for {normalizedProgram}. Coordinator
                        curriculum-grounded review will be skipped. SME, GAD, and ITSO will still
                        evaluate the SLM. The result is marked partial and remains advisory.
                      </span>
                    </span>
                  </label>
                  {allowPartial ? (
                    <label className="flex items-start gap-3 border-t border-[#f2c811]/40 pt-3 text-xs font-semibold text-slate-800">
                      <input
                        type="checkbox"
                        checked={partialChoiceAcknowledged}
                        onChange={(event) => setPartialChoiceAcknowledged(event.target.checked)}
                        className="mt-0.5 size-4 shrink-0 accent-[#1b3b87]"
                        aria-describedby="partial-acknowledgement-help"
                      />
                      <span id="partial-acknowledgement-help" className="min-w-0 leading-relaxed">
                        I understand that the Coordinator agent will be skipped and the evaluation
                        will be reported as a partial result.
                      </span>
                    </label>
                  ) : null}
                  <p
                    id="partial-mode-warning"
                    className="flex items-start gap-2 border-t border-[#f2c811]/40 pt-3 text-xs font-semibold text-slate-800"
                  >
                    <ShieldAlert
                      className="mt-0.5 size-4 shrink-0 text-[#b91c1c]"
                      aria-hidden="true"
                    />
                    <span className="leading-relaxed">
                      Partial validation never claims curriculum-grounded Coordinator review
                      occurred. Pick a different program above to use a ready curriculum instead.
                    </span>
                  </p>
                </fieldset>
              ) : null}
              <button
                type="button"
                onClick={handleStart}
                disabled={!canSubmitEvaluation || validationMutation.isPending}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              >
                {validationMutation.isPending || !uploadedDocumentReady ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Play className="size-4" />
                )}
                {validationMutation.isPending
                  ? 'Starting…'
                  : !uploadedDocumentReady
                    ? 'Waiting for SLM…'
                    : 'Start model validation'}
              </button>
            </div>
          )}

          {error ? (
            <p
              role="alert"
              className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]"
            >
              {getErrorMessage(error, 'Unable to start model validation.')}
            </p>
          ) : null}
        </form>
      </details>

      {activeValidations.map((validation) => (
        <AgentProgressPanel key={validation.validation_id} validation={validation} />
      ))}

      <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Validation history
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
              <tr>
                <th className="px-4 py-3">SLM</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Criteria</th>
                <th className="px-4 py-3 text-right">Compared</th>
                <th className="px-4 py-3 text-right">Exact</th>
                <th className="px-4 py-3 text-right">Mean error</th>
                <th className="px-4 py-3 text-right">Latency</th>
                <th className="px-4 py-3 text-right">Perplexity</th>
                <th className="px-4 py-3 text-right">Toxicity</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {history.isLoading ? (
                <tr>
                  <td
                    colSpan={HISTORY_COLSPAN}
                    className="px-4 py-8 text-center font-semibold text-slate-600"
                  >
                    Loading validation history…
                  </td>
                </tr>
              ) : null}
              {history.isError ? (
                <tr>
                  <td
                    colSpan={HISTORY_COLSPAN}
                    className="px-4 py-8 text-center font-semibold text-[#b91c1c]"
                  >
                    Unable to load validation history.
                  </td>
                </tr>
              ) : null}
              {history.data?.items.map((item) => {
                const compared = item.criterion_scores.filter(
                  (score) => score.actual_score != null,
                );
                const exactMatches = compared.filter(
                  (score) => score.actual_score === score.expected_score,
                ).length;
                const isExpanded = expandedValidationId === item.validation_id;
                return (
                  <HistoryRow
                    key={item.validation_id}
                    item={item}
                    isExpanded={isExpanded}
                    isAnyExpanded={expandedValidationId !== null}
                    comparedCount={compared.length}
                    exactMatches={exactMatches}
                    onToggle={() =>
                      setExpandedValidationId((current) =>
                        current === item.validation_id ? null : item.validation_id,
                      )
                    }
                    onClose={() => setExpandedValidationId(null)}
                  />
                );
              })}
              {!history.isLoading && !history.isError && history.data?.items.length === 0 ? (
                <tr>
                  <td
                    colSpan={HISTORY_COLSPAN}
                    className="px-4 py-8 text-center font-semibold text-slate-600"
                  >
                    No validation runs yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function AgentProgressPanel({ validation }: { validation: ModelValidationItem }) {
  const isEvaluating = validation.status === 'EVALUATING';
  const agentsEvaluated = validation.status === 'SYNTHESIZING';

  return (
    <section
      aria-live="polite"
      aria-label={`Agent progress for ${validation.document_title ?? 'Model Validation'}`}
      className="overflow-hidden rounded-sm border border-slate-200 bg-white"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Agent evaluation progress
          </h2>
          <p className="mt-1 text-xs font-medium text-slate-600">
            {validation.document_title ?? 'Untitled SLM'} · Same parallel scoring pipeline as
            faculty evaluation
          </p>
        </div>
        <span
          className={`rounded-sm px-2 py-1 text-xs font-bold ${statusClass(validation.status)}`}
        >
          {validation.status}
        </span>
      </div>

      <div className="grid gap-px bg-slate-200 sm:grid-cols-2 xl:grid-cols-4">
        {validationAgents.map((agent) => {
          const isSkipped = agent.id === 'coordinator' && validation.partial_without_curriculum;
          const label = isSkipped
            ? 'Skipped — no curriculum'
            : isEvaluating
              ? 'Evaluating'
              : agentsEvaluated
                ? 'Agent scoring complete'
                : 'Queued';

          return (
            <div key={agent.id} className="flex min-h-28 items-center gap-3 bg-white p-4">
              {isSkipped || agentsEvaluated ? (
                <CheckCircle
                  className={`size-5 shrink-0 ${isSkipped ? 'text-slate-400' : 'text-[#3b963e]'}`}
                  aria-hidden="true"
                />
              ) : isEvaluating ? (
                <Loader2
                  className="size-5 shrink-0 animate-spin text-[#1b3b87]"
                  aria-hidden="true"
                />
              ) : (
                <span className="size-3 shrink-0 rounded-full border-2 border-slate-400" />
              )}
              <span className="min-w-0">
                <span className="block text-sm font-bold text-slate-900">{agent.label}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-600">{label}</span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <dt className="text-xs font-semibold text-slate-600">{label}</dt>
      <dd className="text-lg font-bold tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}

type ValidationAgentId = (typeof validationAgents)[number]['id'];

function CircularMetric({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color: string;
}) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const boundedValue = value == null ? 0 : Math.min(1, Math.max(0, value));
  const percentage = value == null ? null : boundedValue * 100;

  return (
    <div className="flex min-w-0 items-center gap-3 border border-slate-200 bg-slate-50 p-3">
      <div
        className="relative size-24 shrink-0"
        role="img"
        aria-label={`${label}: ${percentage == null ? 'unavailable' : `${percentage.toFixed(1)} percent`}`}
      >
        <svg className="size-24 -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="butt"
            strokeDasharray={`${boundedValue * circumference} ${circumference}`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-lg font-bold tabular-nums text-slate-900">
          {percentage == null ? '—' : `${percentage.toFixed(1)}%`}
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-800">{label}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600">
          {label === 'Accuracy' ? 'Exact score matches' : 'Macro average by score class'}
        </p>
      </div>
    </div>
  );
}

function ConfusionMatrix({
  labels,
  matrix,
  agentMatrices,
  isLoading,
  isError,
}: {
  labels: string[];
  matrix: number[][];
  agentMatrices?: Record<string, number[][]>;
  isLoading: boolean;
  isError: boolean;
}) {
  const [selectedAgent, setSelectedAgent] = useState<'all' | ValidationAgentId>('all');
  // Pull the per-agent matrix straight from the API response. We never
  // synthesise one from scratch: if the API did not return a 4×4 grid
  // with at least one counted cell, the per-agent breakdown is honest
  // "unavailable" and must not be rendered as a fabricated all-zero
  // table. The aggregate "all" view is allowed to display a real
  // all-zero matrix per the Model Validation spec, so it keeps its
  // current behaviour.
  const perAgentMatrix = selectedAgent === 'all' ? null : (agentMatrices?.[selectedAgent] ?? null);
  const isPerAgentBreakdownMissing =
    selectedAgent !== 'all' && !hasConfusionMatrixData(perAgentMatrix);
  // The matrix consumed for metric calculations and the table intensity
  // must only ever be a real, comparable 4×4 grid. A missing key, the
  // wrong shape, or an all-zero grid are all routed to a fresh empty
  // matrix so the metric helpers either return nulls or — at worst —
  // `0/0` denominators that already short-circuit inside the helper.
  // The aggregate "all" view always uses the API-supplied matrix,
  // including a legitimate all-zero response per the Model Validation
  // spec.
  const displayedMatrix =
    selectedAgent === 'all'
      ? matrix
      : hasConfusionMatrixData(perAgentMatrix)
        ? perAgentMatrix
        : emptyConfusionMatrix();
  const maximum = Math.max(1, ...displayedMatrix.flat());
  const metrics = calculateConfusionMatrixMetrics(displayedMatrix);
  const selectedLabel = selectedAgent === 'all' ? 'All agents' : agentLabel(selectedAgent);

  return (
    <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
          Score confusion matrix
        </h2>
        <p className="mt-1 text-xs text-slate-600">Expected class by predicted class</p>
      </div>
      <div className="overflow-x-auto p-4">
        {isLoading ? (
          <p className="py-16 text-center text-sm font-semibold text-slate-600">
            Loading confusion matrix…
          </p>
        ) : isError ? (
          <p className="py-16 text-center text-sm font-semibold text-[#b91c1c]">
            Unable to load validation metrics.
          </p>
        ) : (
          <div className="grid gap-5">
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Filter confusion matrix by evaluator"
            >
              {[{ id: 'all', label: 'All agents' }, ...validationAgents].map((agent) => {
                const isSelected = selectedAgent === agent.id;
                return (
                  <button
                    key={agent.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelectedAgent(agent.id as 'all' | ValidationAgentId)}
                    className={cn(
                      'rounded-sm border px-3 py-2 text-xs font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                      isSelected
                        ? 'border-[#1b3b87] bg-[#1b3b87] text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50',
                    )}
                  >
                    {agent.label}
                  </button>
                );
              })}
            </div>
            <p className="text-sm font-semibold text-slate-800" aria-live="polite">
              Showing {selectedLabel} score agreement
            </p>
            <div className="grid gap-3 md:grid-cols-3" aria-label="Confusion matrix metrics">
              <CircularMetric label="Accuracy" value={metrics.accuracy} color="#1b3b87" />
              <CircularMetric label="Precision" value={metrics.precision} color="#3b963e" />
              <CircularMetric label="Recall" value={metrics.recall} color="#3eaed4" />
            </div>
            <p className="text-xs leading-relaxed text-slate-600">
              Precision and recall are macro averages across score classes with available samples.
            </p>
            {isPerAgentBreakdownMissing ? (
              <div
                role="status"
                data-testid="per-agent-breakdown-unavailable"
                className="rounded-sm border border-slate-200 bg-slate-50 px-4 py-6 text-center"
              >
                <p className="text-sm font-bold uppercase tracking-wider text-slate-700">
                  Breakdown unavailable
                </p>
                <p className="mt-1 text-xs font-medium leading-relaxed text-slate-600">
                  {selectedLabel} has no recorded expected-vs-actual score pairs yet, so a
                  per-evaluator confusion matrix cannot be drawn. Run a validation against this
                  agent to populate it.
                </p>
              </div>
            ) : (
              <table
                className="mx-auto border-collapse text-center"
                aria-label="Score confusion matrix"
              >
                <thead>
                  <tr>
                    <th className="h-12 w-24 px-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                      Expected ↓
                    </th>
                    {labels.map((label) => (
                      <th
                        key={label}
                        scope="col"
                        className="h-12 min-w-20 border border-slate-200 bg-slate-50 text-sm font-bold text-slate-800"
                      >
                        Predicted {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayedMatrix.map((row, rowIndex) => (
                    <tr key={labels[rowIndex]}>
                      <th
                        scope="row"
                        className="h-20 border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-slate-800"
                      >
                        Expected {labels[rowIndex]}
                      </th>
                      {row.map((count, columnIndex) => {
                        const intensity = count / maximum;
                        const diagonal = rowIndex === columnIndex;
                        return (
                          <td
                            key={`${rowIndex}-${columnIndex}`}
                            className="h-20 min-w-20 border border-slate-200 text-xl font-bold tabular-nums text-slate-900"
                            style={{
                              backgroundColor: diagonal
                                ? `rgba(59, 150, 62, ${0.08 + intensity * 0.48})`
                                : `rgba(242, 200, 17, ${0.05 + intensity * 0.5})`,
                            }}
                            aria-label={`Expected ${labels[rowIndex]}, predicted ${labels[columnIndex]}: ${count}`}
                          >
                            {count}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-4 border-t border-slate-200 px-4 py-3 text-xs font-semibold text-slate-600">
        <span>
          <span className="mr-1 inline-block size-3 border border-[#3b963e] bg-[#3b963e]/30" />
          Agreement
        </span>
        <span>
          <span className="mr-1 inline-block size-3 border border-[#f2c811] bg-[#f2c811]/40" />
          Mismatch
        </span>
      </div>
    </div>
  );
}

type HistoryRowProps = {
  item: ModelValidationItem;
  isExpanded: boolean;
  isAnyExpanded: boolean;
  comparedCount: number;
  exactMatches: number;
  onToggle: () => void;
  onClose: () => void;
};

function HistoryRow({
  item,
  isExpanded,
  isAnyExpanded: _isAnyExpanded,
  comparedCount,
  exactMatches,
  onToggle,
  onClose,
}: HistoryRowProps) {
  const expansionId = `validation-detail-${item.validation_id}`;
  return (
    <>
      <tr className={cn(isExpanded && 'bg-slate-50/60')}>
        <td className="px-4 py-3 font-semibold text-slate-900">
          {item.document_title ?? 'Untitled SLM'}
        </td>
        <td className="px-4 py-3">
          <span
            className={`inline-flex rounded-sm px-2 py-1 text-xs font-bold ${statusClass(item.status)}`}
          >
            {item.status}
          </span>
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.criterion_scores.length}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">{comparedCount}</td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {comparedCount ? `${exactMatches}/${comparedCount}` : '—'}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.absolute_error == null ? '—' : item.absolute_error.toFixed(2)}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.latency_seconds == null ? '—' : `${item.latency_seconds.toFixed(2)} s`}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.score_perplexity == null ? '—' : item.score_perplexity.toFixed(2)}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.toxicity_score == null ? (
            <span title={item.toxicity_error ?? 'Assessment pending'}>—</span>
          ) : (
            <span
              title={`${item.toxicity_label ?? 'Assessed'}: ${item.toxicity_explanation ?? 'No explanation available'}`}
            >
              {(item.toxicity_score * 100).toFixed(2)}%
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-right">
          {item.status === 'COMPLETED' ||
          item.status === 'FAILED' ||
          item.criterion_scores.length > 0 ? (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={isExpanded}
              aria-controls={expansionId}
              className="inline-flex items-center gap-1 rounded-sm font-bold text-[#1b3b87] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            >
              {isExpanded ? (
                <ChevronDown className="size-4" aria-hidden="true" />
              ) : (
                <ChevronRight className="size-4" aria-hidden="true" />
              )}
              {isExpanded ? 'Hide details' : 'Open evaluation'}
            </button>
          ) : item.error_message ? (
            <span className="text-xs font-semibold text-[#b91c1c]">{item.error_message}</span>
          ) : (
            '—'
          )}
        </td>
      </tr>
      {isExpanded ? (
        <tr>
          <td colSpan={HISTORY_COLSPAN} className="bg-slate-50/60 px-0 py-0">
            <ValidationDetail
              id={expansionId}
              validationId={item.validation_id}
              evaluationId={item.evaluation_id}
              fallbackCriteria={item.criterion_scores}
              partialWithoutCurriculum={item.partial_without_curriculum}
              overallStatus={item.status}
              errorMessage={item.error_message}
              isExpanded={isExpanded}
              onClose={onClose}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

type ValidationDetailProps = {
  id: string;
  validationId: string;
  evaluationId: string;
  fallbackCriteria: ModelValidationCriterionScore[];
  partialWithoutCurriculum: boolean;
  overallStatus: ModelValidationItem['status'];
  errorMessage: string | null;
  isExpanded: boolean;
  onClose: () => void;
};

function ValidationDetail({
  id,
  validationId,
  evaluationId,
  fallbackCriteria,
  partialWithoutCurriculum,
  overallStatus,
  errorMessage,
  isExpanded,
  onClose,
}: ValidationDetailProps) {
  const detailQuery = useQuery<ModelValidationItem>({
    queryKey: ['admin', 'model-validation', validationId],
    queryFn: () => adminApi.getModelValidation(validationId),
    // Always lazy-load via the new detail endpoint on expand. Avoids
    // preloading every run's full criterion list on mount.
    enabled: isExpanded,
    staleTime: 60_000,
  });

  const evaluationQuery = useQuery<AdminEvaluationResponse>({
    queryKey: ['admin', 'model-validation-evaluation', validationId],
    queryFn: () => adminApi.getModelValidationEvaluation(validationId),
    enabled: isExpanded,
    staleTime: 60_000,
  });

  // Prefer the dedicated detail endpoint's criterion list; fall back to the
  // list data only if the detail query is still loading on the first render
  // so the table is never empty for runs the list already cached.
  const criteria = detailQuery.data?.criterion_scores?.length
    ? detailQuery.data.criterion_scores
    : fallbackCriteria;
  const grouped = groupCriteriaByAgent(criteria);
  const isTerminal = overallStatus === 'COMPLETED' || overallStatus === 'FAILED';
  const evaluation = evaluationQuery.data;
  const isCoordinatorSkipped = partialWithoutCurriculum;

  return (
    <section
      id={id}
      role="region"
      aria-label={`Validation details for ${validationId}`}
      className="grid gap-4 border-t border-slate-200 bg-white px-4 py-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Per-agent criterion detail
          </h3>
          <p className="mt-1 text-xs font-medium text-slate-600">
            Expected vs. actual scores for every agent criterion. Pending values reflect evaluation
            state; unavailable values reflect completed runs that did not record a score.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-sm border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
        >
          Close
        </button>
      </div>

      {isCoordinatorSkipped ? (
        <p
          role="note"
          className="flex items-start gap-2 rounded-sm border border-[#f2c811] bg-[#f2c811]/10 px-3 py-2 text-xs font-semibold text-slate-800"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[#1e293b]" aria-hidden="true" />
          <span className="leading-relaxed">
            This validation ran without a curriculum reference. Coordinator curriculum-grounded
            review was skipped. SME, GAD, and ITSO scores below are from the partial run.
          </span>
        </p>
      ) : null}

      {detailQuery.isLoading ? (
        <p
          role="status"
          className="flex items-center gap-2 rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600"
        >
          <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
          Loading criterion detail…
        </p>
      ) : null}

      {detailQuery.isError ? (
        <p
          role="alert"
          className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-3 py-2 text-xs font-semibold text-[#b91c1c]"
        >
          {getErrorMessage(
            detailQuery.error,
            'Unable to load the criterion detail for this validation.',
          )}
        </p>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {grouped.map(({ agentId, agentName, criteria: agentCriteria }) => {
          const isAgentSkipped = agentId === 'coordinator' && isCoordinatorSkipped;
          return (
            <article key={agentId} className="overflow-hidden rounded-sm border border-slate-200">
              <header className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  {agentName}
                </h4>
                {isAgentSkipped ? (
                  <span className="inline-flex items-center gap-1 rounded-sm bg-slate-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-700">
                    <ShieldAlert className="size-3" aria-hidden="true" />
                    Skipped — no curriculum
                  </span>
                ) : null}
              </header>
              {isAgentSkipped ? (
                <p className="px-3 py-3 text-xs font-medium leading-relaxed text-slate-600">
                  Coordinator scoring was skipped for this run. No expected, actual, or error values
                  are reported.
                </p>
              ) : (
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="bg-white text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Criterion</th>
                      <th className="px-3 py-2 text-right">Expected</th>
                      <th className="px-3 py-2 text-right">Actual</th>
                      <th className="px-3 py-2 text-right">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {agentCriteria.map((score) => {
                      const expected = score.expected_score;
                      const actual = score.actual_score;
                      const error = score.absolute_error;
                      const actualLabel =
                        actual == null ? (isTerminal ? 'Unavailable' : 'Pending') : String(actual);
                      const errorLabel =
                        error == null ? (isTerminal ? 'Unavailable' : 'Pending') : error.toFixed(2);
                      return (
                        <tr key={score.expected_score_id}>
                          <th scope="row" className="px-3 py-2 font-semibold text-slate-900">
                            <span className="block break-words">
                              {score.criterion_id} · {score.criterion_title}
                            </span>
                          </th>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {expected}
                          </td>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {actual == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-[#b91c1c]/10 text-[#b91c1c]'
                                    : 'bg-slate-100 text-slate-600',
                                )}
                              >
                                {actualLabel}
                              </span>
                            ) : (
                              actualLabel
                            )}
                          </td>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {error == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-[#b91c1c]/10 text-[#b91c1c]'
                                    : 'bg-slate-100 text-slate-600',
                                )}
                              >
                                {errorLabel}
                              </span>
                            ) : (
                              errorLabel
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {agentCriteria.length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-3 py-3 text-center text-xs font-medium text-slate-500"
                        >
                          No criteria recorded for this agent.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              )}
            </article>
          );
        })}
        {grouped.length === 0 ? (
          <p className="rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
            No criteria have been recorded for this validation yet.
          </p>
        ) : null}
      </div>

      <section
        aria-label="Linked evaluation"
        className="grid gap-3 rounded-sm border border-slate-200 bg-white p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Linked evaluation
          </h3>
          {evaluation ? (
            <span
              className={`inline-flex rounded-sm px-2 py-1 text-xs font-bold ${statusClass(evaluation.status as ModelValidationItem['status'])}`}
            >
              {evaluation.status}
            </span>
          ) : evaluationQuery.isLoading ? (
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
              <Loader2 className="size-3 animate-spin text-[#1b3b87]" aria-hidden="true" />
              Loading evaluation status…
            </span>
          ) : null}
        </div>
        <p className="text-xs leading-relaxed text-slate-600">
          The evaluation job is accessed through the admin-linked evaluation endpoint so admins can
          review benchmark runs that another admin submitted. Faculty cannot reach this surface.
        </p>
        {evaluationQuery.isError ? (
          <p
            role="alert"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-3 py-2 text-xs font-semibold text-[#b91c1c]"
          >
            {getErrorMessage(
              evaluationQuery.error,
              'Unable to load the linked evaluation for this validation.',
            )}
          </p>
        ) : null}
        {evaluation ? (
          <dl className="grid gap-2 sm:grid-cols-2">
            <EvaluationMetaItem label="Evaluation ID" value={evaluation.evaluation_id} mono />
            <EvaluationMetaItem label="Status" value={evaluation.status} emphasize />
            <EvaluationMetaItem
              label="Submitted"
              value={formatTimestamp(evaluation.submitted_at)}
            />
            <EvaluationMetaItem
              label="Completed"
              value={formatTimestamp(evaluation.completed_at)}
            />
            <EvaluationMetaItem
              label="Duration"
              value={
                evaluation.duration_seconds == null
                  ? '—'
                  : `${evaluation.duration_seconds.toFixed(2)} s`
              }
            />
            <EvaluationMetaItem
              label="Partial"
              value={evaluation.partial_without_curriculum ? 'Yes' : 'No'}
            />
            {evaluation.partial_reason ? (
              <EvaluationMetaItem
                label="Partial reason"
                value={evaluation.partial_reason}
                fullWidth
              />
            ) : null}
            {evaluation.error_message ? (
              <EvaluationMetaItem label="Error" value={evaluation.error_message} error fullWidth />
            ) : null}
            {errorMessage && !evaluation.error_message ? (
              <EvaluationMetaItem label="Run error" value={errorMessage} error fullWidth />
            ) : null}
          </dl>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3 text-xs font-semibold text-slate-700">
          <Link
            to="/evaluations/$id"
            params={{ id: evaluationId }}
            className="inline-flex items-center gap-1 rounded-sm border border-slate-200 bg-white px-3 py-1.5 font-bold text-[#1b3b87] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
          >
            Open scorecard
          </Link>
          <span className="text-xs font-medium text-slate-500">
            Opens the evaluation scorecard for this validation.
          </span>
        </div>
      </section>
    </section>
  );
}

type GroupedCriteria = {
  agentId: string;
  agentName: string;
  criteria: ModelValidationCriterionScore[];
};

function groupCriteriaByAgent(scores: ModelValidationCriterionScore[]): GroupedCriteria[] {
  const buckets = new Map<string, ModelValidationCriterionScore[]>();
  for (const score of scores) {
    const list = buckets.get(score.agent_id) ?? [];
    list.push(score);
    buckets.set(score.agent_id, list);
  }
  const ordered: GroupedCriteria[] = [];
  for (const agent of validationAgents) {
    const items = buckets.get(agent.id);
    if (items && items.length > 0) {
      ordered.push({
        agentId: agent.id,
        agentName: agent.label,
        criteria: [...items].sort((a, b) => a.criterion_id.localeCompare(b.criterion_id)),
      });
      buckets.delete(agent.id);
    }
  }
  for (const [agentId, criteria] of buckets.entries()) {
    ordered.push({
      agentId,
      agentName: agentLabel(agentId),
      criteria: [...criteria].sort((a, b) => a.criterion_id.localeCompare(b.criterion_id)),
    });
  }
  return ordered;
}

function EvaluationMetaItem({
  label,
  value,
  mono = false,
  emphasize = false,
  error = false,
  fullWidth = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  emphasize?: boolean;
  error?: boolean;
  fullWidth?: boolean;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-[7rem_1fr] items-baseline gap-2 border-b border-slate-200 pb-2 last:border-b-0',
        fullWidth && 'sm:col-span-2',
      )}
    >
      <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd
        className={cn(
          'text-xs leading-relaxed',
          mono && 'font-mono break-all text-slate-700',
          emphasize && 'font-semibold text-slate-900',
          !mono && !emphasize && 'font-medium text-slate-700',
          error && 'font-semibold text-[#b91c1c]',
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
