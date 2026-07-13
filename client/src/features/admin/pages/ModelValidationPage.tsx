import { useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from 'react';
import { Link } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, ChevronDown, FileCheck2, Loader2, Play, Upload } from 'lucide-react';
import { documentsApi } from '@/shared/api/documents.api';
import { getErrorMessage } from '@/shared/api/http';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import type {
  CurriculumSuggestionResponse,
  DocumentUploadResponse,
} from '@/shared/types/documents';
import { adminApi } from '../api/admin.api';
import type { ModelValidationCreateBody, ModelValidationItem } from '../types';

const terminalStatuses = new Set(['COMPLETED', 'FAILED']);
const criterionKey = (agentId: string, criterionId: string) => `${agentId}:${criterionId}`;
const validationAgents = [
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'gad', label: 'GAD Evaluator' },
  { id: 'itso', label: 'IT Security Officer' },
] as const;

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
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [expectedScores, setExpectedScores] = useState<Record<string, string>>({});
  const [uploaded, setUploaded] = useState<DocumentUploadResponse | null>(null);
  const [suggestions, setSuggestions] = useState<CurriculumSuggestionResponse | null>(null);
  const [curriculumId, setCurriculumId] = useState('');
  const [allowPartial, setAllowPartial] = useState(false);

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
      const suggestionResponse = await documentsApi.getCurriculumSuggestion(
        document.documentId,
        input.program,
      );
      return { document, suggestionResponse };
    },
    onSuccess: ({ document, suggestionResponse }) => {
      setUploaded(document);
      setSuggestions(suggestionResponse);
      setCurriculumId(
        suggestionResponse.preferredSuggestion?.documentId ??
          suggestionResponse.curriculumSuggestions[0]?.documentId ??
          '',
      );
      setAllowPartial(suggestionResponse.curriculumSuggestions.length === 0);
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
      setSuggestions(null);
      setCurriculumId('');
      setAllowPartial(false);
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
  const uploadedProcessingStatus =
    uploadedDocument.data?.processingStatus ?? uploaded?.processingStatus;
  const uploadedDocumentReady =
    uploadedProcessingStatus === 'PROCESSED' && (uploadedDocument.data?.chunks.length ?? 0) > 0;
  const canSubmitEvaluation =
    uploadedDocumentReady &&
    allCriterionScoresComplete &&
    (!!curriculumId || (allowPartial && readyCurricula.length === 0));
  const error = uploadMutation.error ?? uploadedDocument.error ?? validationMutation.error;
  const activeValidations =
    history.data?.items.filter((item) => !terminalStatuses.has(item.status)) ?? [];

  const resetPreparedUpload = () => {
    setFile(null);
    setUploaded(null);
    setSuggestions(null);
    setCurriculumId('');
    setAllowPartial(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploaded(null);
    setSuggestions(null);
    if (nextFile && !title.trim()) setTitle(nextFile.name.replace(/\.pdf$/i, ''));
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
      partial_without_curriculum: !curriculumId && allowPartial,
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
            <p>Score perplexity is e raised to mean absolute score error; 1.00 is ideal.</p>
            <p>Toxicity is assessed contextually by the configured model and remains advisory.</p>
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
        <form
          onSubmit={handlePrepare}
          className="grid min-w-0 gap-5 border-t border-slate-200 p-5"
        >
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
            onChange={setProgram}
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
              {readyCurricula.length ? (
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
              ) : (
                <label className="flex items-start gap-3 rounded-sm border border-[#f2c811] bg-[#f2c811]/10 p-3 text-sm font-semibold text-slate-800">
                  <input
                    type="checkbox"
                    checked={allowPartial}
                    onChange={(event) => setAllowPartial(event.target.checked)}
                    className="mt-1"
                  />
                  Continue with a partial validation. Coordinator review will be skipped because no
                  indexed curriculum matches this program.
                </label>
              )}
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
                  <td colSpan={10} className="px-4 py-8 text-center font-semibold text-slate-600">
                    Loading validation history…
                  </td>
                </tr>
              ) : null}
              {history.isError ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center font-semibold text-[#b91c1c]">
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
                return (
                  <tr key={item.validation_id}>
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
                    <td className="px-4 py-3 text-right font-semibold tabular-nums">
                      {compared.length}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold tabular-nums">
                      {compared.length ? `${exactMatches}/${compared.length}` : '—'}
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
                      {item.status === 'COMPLETED' ? (
                        <Link
                          to="/evaluations/$id"
                          params={{ id: item.evaluation_id }}
                          className="font-bold text-[#1b3b87] hover:underline"
                        >
                          View scorecard
                        </Link>
                      ) : item.error_message ? (
                        <span className="text-xs font-semibold text-[#b91c1c]">
                          {item.error_message}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                );
              })}
              {!history.isLoading && !history.isError && history.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center font-semibold text-slate-600">
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

function ConfusionMatrix({
  labels,
  matrix,
  isLoading,
  isError,
}: {
  labels: string[];
  matrix: number[][];
  isLoading: boolean;
  isError: boolean;
}) {
  const maximum = Math.max(1, ...matrix.flat());

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
              {matrix.map((row, rowIndex) => (
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
