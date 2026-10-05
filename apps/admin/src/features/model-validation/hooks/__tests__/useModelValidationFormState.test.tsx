// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { KeyboardEvent, ReactNode } from 'react';
import { useModelValidationFormState } from '../useModelValidationFormState';
import { modelValidationApi } from '../../api/modelValidation.api';
import { documentsApi } from '@equiped/api-client';
import { ApiError } from '@equiped/api-client';
import type { ClientDocument } from '@equiped/types';
import type {
  AdapterChoiceList,
  ModelValidationCreateBody,
  ModelValidationCriteriaResponse,
  ModelValidationItem,
} from '../../types';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockReadyDoc: ClientDocument = {
  documentId: 'doc-ready-1',
  title: 'SLM 1',
  sourceType: 'slm',
  processingStatus: 'PROCESSED',
  academicYear: null,
  courseCode: null,
  courseTitle: null,
  lessonTitle: null,
  program: null,
  pageCount: 1,
  hasOcrPages: false,
  uploadedAt: '2026-08-30T00:00:00Z',
  chunks: [
    {
      chunkId: 'c-1',
      documentId: 'doc-ready-1',
      sourceType: 'slm',
      agentDomain: 'sme',
      pageNumber: 1,
      text: 'Text chunk 1',
      tokenCount: 10,
      isOcr: false,
    },
  ],
};

const mockCriteriaCatalog: ModelValidationCriteriaResponse = {
  agents: [
    {
      agent_id: 'sme',
      agent_name: 'Subject Matter Expert',
      rubric_set_id: 'set-sme-123',
      rubric_version: 1,
      domains: [
        {
          rubric_domain_id: 'dom-sme-1',
          code: 'CONTENT',
          title: 'Content Quality',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-sme-1',
              criterion_code: 'SME_1',
              criterion_id: 'crit-sme-1',
              title: 'Accuracy',
              description: 'Check content accuracy',
              display_order: 1,
            },
          ],
        },
      ],
      criteria: [
        {
          rubric_criterion_id: 'crit-sme-1',
          criterion_code: 'SME_1',
          criterion_id: 'crit-sme-1',
          title: 'Accuracy',
          description: 'Check content accuracy',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'coordinator',
      agent_name: 'Program Coordinator',
      rubric_set_id: 'set-coord-123',
      rubric_version: 1,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-coord-1',
          criterion_code: 'COORD_1',
          criterion_id: 'crit-coord-1',
          title: 'Curriculum Alignment',
          description: 'Check curriculum alignment',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'gad',
      agent_name: 'GAD',
      rubric_set_id: 'set-gad-123',
      rubric_version: 2,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-gad-1',
          criterion_code: 'GAD_1',
          criterion_id: 'crit-gad-1',
          title: 'Inclusivity',
          description: 'Check gender sensitivity',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'itso',
      agent_name: 'ITSO',
      rubric_set_id: 'set-itso-123',
      rubric_version: 1,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-itso-1',
          criterion_code: 'ITSO_1',
          criterion_id: 'crit-itso-1',
          title: 'Data Security',
          description: 'Check data privacy',
          display_order: 1,
        },
      ],
    },
  ],
  total_criteria: 4,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const mockAdapterChoices: AdapterChoiceList = {
  agent_id: 'sme',
  server_reachable: true,
  adapters: [
    {
      adapter_id: 'sme-v1',
      version: 1,
      loaded: false,
      published: false,
      gguf_filename: 'sme-v1.gguf',
    },
    {
      adapter_id: 'sme-v2',
      version: 2,
      loaded: null,
      published: false,
      gguf_filename: 'sme-v2.gguf',
    },
    {
      adapter_id: 'sme-v3',
      version: 3,
      loaded: true,
      published: true,
      gguf_filename: 'sme-v3.gguf',
    },
    {
      adapter_id: 'sme-v4',
      version: 4,
      loaded: true,
      published: false,
      gguf_filename: 'sme-v4.gguf',
    },
  ],
};

function mockCatalog() {
  vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(mockCriteriaCatalog);
}

function mockAdapters(list: AdapterChoiceList = mockAdapterChoices) {
  return vi.spyOn(modelValidationApi, 'listAdapterChoices').mockResolvedValue(list);
}

function mockUploadedReadyDocument() {
  vi.spyOn(documentsApi, 'uploadDocument').mockResolvedValue({
    documentId: 'doc-ready-1',
    title: 'SLM 1',
    sourceType: 'slm',
    processingStatus: 'PROCESSED',
    academicYear: null,
    courseCode: null,
    courseTitle: null,
    lessonTitle: null,
  });
  vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
}

function captureSubmittedBody() {
  const captured: { body?: ModelValidationCreateBody } = {};
  vi.spyOn(modelValidationApi, 'createModelValidation').mockImplementation(async (body) => {
    captured.body = body;
    const created: ModelValidationItem = {
      validation_id: 'val-1',
      evaluation_id: 'eval-1',
      document_id: body.document_id,
      document_title: 'SLM 1',
      model_variant: body.model_variant,
      adapter_id: body.adapter_id ?? null,
      adapter_label: null,
      adapter_resolution: null,
      compare_group_id: null,
      partial_without_curriculum: body.partial_without_curriculum,
      bound_forms: [],
      criterion_scores: [],
      absolute_error: null,
      latency_seconds: null,
      score_perplexity: null,
      toxicity_score: null,
      toxicity_label: null,
      toxicity_explanation: null,
      toxicity_model: null,
      toxicity_error: null,
      status: 'SUBMITTED',
      error_message: null,
      created_at: '2026-09-29T00:00:00Z',
    };
    return created;
  });
  return captured;
}

type HookResult = { current: ReturnType<typeof useModelValidationFormState> };

async function uploadDocument(result: HookResult) {
  await act(async () => {
    result.current.uploadMutation.mutate({
      file: new File(['dummy'], 'slm.pdf', { type: 'application/pdf' }),
      title: 'SLM 1',
      program: 'BSCS',
    });
  });
  await waitFor(() => {
    expect(result.current.uploadedDocumentReady).toBe(true);
  });
}

async function renderReady() {
  mockCatalog();
  mockAdapters();
  mockUploadedReadyDocument();
  const captured = captureSubmittedBody();
  const rendered = renderHook(() => useModelValidationFormState(), {
    wrapper: createWrapper(),
  });
  await waitFor(() => expect(rendered.result.current.criterionCatalog.isSuccess).toBe(true));
  await uploadDocument(rendered.result);
  return { ...rendered, captured };
}

async function chooseSmeWithScores(result: HookResult) {
  act(() => {
    result.current.setTargetAgent('sme');
    result.current.setExpectedScores({ 'sme:crit-sme-1': '4' });
  });
  await waitFor(() => expect(result.current.adapterChoices.isSuccess).toBe(true));
}

describe('useModelValidationFormState', () => {
  it('starts with no target and no criteria, and never offers an all-agents scope', async () => {
    mockCatalog();
    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));

    expect(result.current.targetAgent).toBeNull();
    expect(result.current.criterionDefinitions).toEqual([]);
    expect(result.current.modelChoice).toBe('base');
    expect(result.current.canSubmitEvaluation).toBe(false);
  });

  it('scopes criteria to the single chosen agent, never Coordinator', async () => {
    mockCatalog();
    mockAdapters();
    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));

    act(() => result.current.setTargetAgent('gad'));
    expect(result.current.criterionDefinitions.map((a) => a.agent_id)).toEqual(['gad']);
  });

  it('builds base, published and per-version options from the agent adapter list', async () => {
    mockCatalog();
    const adaptersSpy = mockAdapters();
    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));

    // No agent chosen yet: the adapter list is not requested.
    expect(adaptersSpy).not.toHaveBeenCalled();

    act(() => result.current.setTargetAgent('sme'));
    await waitFor(() => expect(result.current.adapterChoices.isSuccess).toBe(true));
    expect(adaptersSpy).toHaveBeenCalledWith('sme');

    const options = result.current.adapterOptions;
    expect(options.map((o) => o.value)).toEqual([
      'base',
      'published',
      'sme-v1',
      'sme-v2',
      'sme-v3',
      'sme-v4',
    ]);
    expect(options.find((o) => o.value === 'published')).toMatchObject({
      label: 'Published (v3)',
      disabled: false,
    });
    const disabled = Object.fromEntries(
      options.map((o) => [o.value, 'disabled' in o && o.disabled]),
    );
    expect(disabled).toMatchObject({
      base: false,
      'sme-v1': true, // loaded === false
      'sme-v2': true, // loaded === null (unknown)
      'sme-v3': false,
      'sme-v4': false,
    });
  });

  it('omits the Published option when nothing is published, and disables it when not loaded', async () => {
    mockCatalog();
    const adaptersSpy = mockAdapters({
      agent_id: 'sme',
      server_reachable: true,
      adapters: [
        {
          adapter_id: 'sme-v1',
          version: 1,
          loaded: true,
          published: false,
          gguf_filename: 'a',
        },
      ],
    });
    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));
    act(() => result.current.setTargetAgent('sme'));
    await waitFor(() => expect(result.current.adapterChoices.isSuccess).toBe(true));
    expect(result.current.adapterOptions.map((o) => o.value)).toEqual(['base', 'sme-v1']);

    adaptersSpy.mockResolvedValue({
      agent_id: 'gad',
      server_reachable: true,
      adapters: [
        {
          adapter_id: 'gad-v1',
          version: 1,
          loaded: false,
          published: true,
          gguf_filename: 'g',
        },
      ],
    });
    act(() => result.current.setTargetAgent('gad'));
    await waitFor(() =>
      expect(result.current.adapterOptions.some((o) => o.value === 'published')).toBe(true),
    );
    expect(result.current.adapterOptions.find((o) => o.value === 'published')).toMatchObject({
      disabled: true,
    });
  });

  it('posts a base run with no adapter_id', async () => {
    const { result, captured } = await renderReady();
    await chooseSmeWithScores(result);

    expect(result.current.canSubmitEvaluation).toBe(true);
    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body).toMatchObject({
      document_id: 'doc-ready-1',
      partial_without_curriculum: false,
      target_agent: 'sme',
      model_variant: 'base',
    });
    expect(captured.body).not.toHaveProperty('adapter_id');
    expect(captured.body?.expected_scores).toEqual([
      {
        agent_id: 'sme',
        rubric_set_id: 'set-sme-123',
        rubric_criterion_id: 'crit-sme-1',
        expected_score: 4,
      },
    ]);
  });

  it('posts the published adapter id when the Published choice is used', async () => {
    const { result, captured } = await renderReady();
    await chooseSmeWithScores(result);

    act(() => result.current.setModelChoice('published'));
    expect(result.current.canSubmitEvaluation).toBe(true);
    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body).toMatchObject({
      model_variant: 'adapter',
      adapter_id: 'sme-v3',
      target_agent: 'sme',
    });
  });

  it('posts the chosen version id when a specific version is used', async () => {
    const { result, captured } = await renderReady();
    await chooseSmeWithScores(result);

    act(() => result.current.setModelChoice('sme-v4'));
    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body).toMatchObject({
      model_variant: 'adapter',
      adapter_id: 'sme-v4',
    });
  });

  it('resets the model choice to base when the target agent changes', async () => {
    const { result } = await renderReady();
    await chooseSmeWithScores(result);
    act(() => result.current.setModelChoice('sme-v4'));
    expect(result.current.modelChoice).toBe('sme-v4');

    act(() => result.current.setTargetAgent('gad'));
    expect(result.current.modelChoice).toBe('base');
  });

  it('blocks submission when the chosen version is not loaded', async () => {
    const { result, captured } = await renderReady();
    await chooseSmeWithScores(result);

    act(() => result.current.setModelChoice('sme-v1'));
    expect(result.current.allCriterionScoresComplete).toBe(true);
    expect(result.current.canSubmitEvaluation).toBe(false);

    await act(async () => {
      result.current.handleStart();
    });
    expect(captured.body).toBeUndefined();

    act(() => result.current.setModelChoice('sme-v4'));
    expect(result.current.canSubmitEvaluation).toBe(true);
  });

  it('blocks submission until an agent is chosen', async () => {
    const { result } = await renderReady();
    expect(result.current.targetAgent).toBeNull();
    expect(result.current.canSubmitEvaluation).toBe(false);
  });

  it('blocks submission when the chosen agent is missing from the catalog', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue({
      agents: mockCriteriaCatalog.agents.filter((agent) => agent.agent_id !== 'gad'),
      total_criteria: 3,
    });
    mockAdapters();

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));

    act(() => result.current.setTargetAgent('gad'));

    expect(result.current.criterionDefinitions).toEqual([]);
    expect(result.current.allCriterionScoresComplete).toBe(false);
    expect(result.current.canSubmitEvaluation).toBe(false);
  });

  it('detects stale 409/422 errors and allows catalog reload', async () => {
    mockCatalog();
    mockAdapters();
    mockUploadedReadyDocument();
    const apiError = new ApiError('Conflict: rubric revision changed', {
      status: 409,
      payload: { detail: 'Rubric revision updated' },
    });
    vi.spyOn(modelValidationApi, 'createModelValidation').mockRejectedValue(apiError);

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));
    await uploadDocument(result);
    await chooseSmeWithScores(result);

    await act(async () => {
      result.current.handleStart();
    });
    await waitFor(() => {
      expect(result.current.isStaleBinding).toBe(true);
    });

    const refetchSpy = vi.spyOn(result.current.criterionCatalog, 'refetch');
    await act(async () => {
      await result.current.handleReloadCatalog();
    });
    expect(refetchSpy).toHaveBeenCalled();
  });
});

it('advances to registered score inputs and releases them when unmounted', async () => {
  const smeAgent = mockCriteriaCatalog.agents[0];
  vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue({
    agents: [
      {
        ...smeAgent,
        domains: [],
        criteria: [
          ...smeAgent.criteria,
          {
            ...smeAgent.criteria[0],
            rubric_criterion_id: 'crit-sme-2',
            criterion_id: 'crit-sme-2',
          },
        ],
      },
    ],
    total_criteria: 2,
  });
  mockAdapters();
  const { result } = renderHook(() => useModelValidationFormState(), {
    wrapper: createWrapper(),
  });
  await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));
  act(() => result.current.setTargetAgent('sme'));
  await waitFor(() => expect(result.current.criterionDefinitions.length).toBe(1));

  const nextInput = document.createElement('input');
  const focus = vi.spyOn(nextInput, 'focus');
  const select = vi.spyOn(nextInput, 'select');
  const event = {
    key: 'Enter',
    preventDefault: vi.fn(),
  } as unknown as KeyboardEvent<HTMLInputElement>;
  result.current.registerScoreInput('sme:crit-sme-2', nextInput);
  result.current.handleScoreKeyDown(event, 'sme:crit-sme-1');
  expect(event.preventDefault).toHaveBeenCalled();
  expect(focus).toHaveBeenCalledOnce();
  expect(select).toHaveBeenCalledOnce();

  result.current.registerScoreInput('sme:crit-sme-2', null);
  result.current.handleScoreKeyDown(event, 'sme:crit-sme-1');
  expect(focus).toHaveBeenCalledOnce();
});

function historyItem(overrides: Partial<ModelValidationItem> = {}): ModelValidationItem {
  return {
    validation_id: 'val-old',
    evaluation_id: 'eval-old',
    document_id: 'doc-ready-1',
    document_title: 'SLM 1',
    model_variant: 'adapter',
    adapter_id: 'sme-v3',
    adapter_label: 'v3',
    adapter_resolution: null,
    compare_group_id: null,
    partial_without_curriculum: false,
    bound_forms: [],
    criterion_scores: [
      {
        expected_score_id: 'es-1',
        agent_id: 'sme',
        rubric_set_id: 'set-sme-123',
        rubric_criterion_id: 'crit-sme-1',
        criterion_id: 'crit-sme-1',
        criterion_title: 'Accuracy',
        expected_score: 3,
        actual_score: 2,
        absolute_error: 1,
      },
    ],
    absolute_error: 1,
    latency_seconds: 1,
    score_perplexity: null,
    toxicity_score: null,
    toxicity_label: null,
    toxicity_explanation: null,
    toxicity_model: null,
    toxicity_error: null,
    status: 'COMPLETED',
    error_message: null,
    created_at: '2026-09-29T00:00:00Z',
    ...overrides,
  };
}

describe('preloadFromRun', () => {
  async function renderEmpty() {
    mockCatalog();
    mockAdapters();
    const upload = vi.spyOn(documentsApi, 'uploadDocument');
    const captured = captureSubmittedBody();
    const rendered = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(rendered.result.current.criterionCatalog.isSuccess).toBe(true));
    return { ...rendered, upload, captured };
  }

  it('fills agent, title, program, scores and the stored document, leaving Model unselected', async () => {
    const { result, upload } = await renderEmpty();
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue({
      ...mockReadyDoc,
      program: 'BSCS',
    });

    await act(async () => {
      await result.current.preloadFromRun(historyItem());
    });

    expect(result.current.targetAgent).toBe('sme');
    expect(result.current.title).toBe('SLM 1');
    expect(result.current.program).toBe('BSCS');
    expect(result.current.expectedScores).toEqual({ 'sme:crit-sme-1': '3' });
    expect(result.current.uploaded?.documentId).toBe('doc-ready-1');
    expect(result.current.usingStoredDocument).toBe(true);
    expect(result.current.modelChoice).toBe('');
    expect(result.current.preloadError).toBeNull();
    expect(upload).not.toHaveBeenCalled();
    await waitFor(() => expect(result.current.uploadedDocumentReady).toBe(true));
  });

  it('stays blocked until a Model is chosen, then posts the same document_id with edited scores', async () => {
    const { result, captured } = await renderEmpty();
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
    await act(async () => {
      await result.current.preloadFromRun(historyItem());
    });
    await waitFor(() => expect(result.current.uploadedDocumentReady).toBe(true));
    await waitFor(() => expect(result.current.adapterChoices.isSuccess).toBe(true));

    expect(result.current.allCriterionScoresComplete).toBe(true);
    expect(result.current.canSubmitEvaluation).toBe(false);
    await act(async () => {
      result.current.handleStart();
    });
    expect(captured.body).toBeUndefined();

    act(() => {
      result.current.setExpectedScores({ 'sme:crit-sme-1': '4' });
      result.current.setModelChoice('sme-v4');
    });
    expect(result.current.canSubmitEvaluation).toBe(true);
    await act(async () => {
      result.current.handleStart();
    });
    expect(captured.body).toMatchObject({
      document_id: 'doc-ready-1',
      target_agent: 'sme',
      model_variant: 'adapter',
      adapter_id: 'sme-v4',
    });
    expect(captured.body?.expected_scores[0].expected_score).toBe(4);
  });

  it('"Use a different file" (resetPreparedUpload) drops the stored document', async () => {
    const { result } = await renderEmpty();
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
    await act(async () => {
      await result.current.preloadFromRun(historyItem());
    });
    expect(result.current.usingStoredDocument).toBe(true);

    act(() => result.current.resetPreparedUpload());
    expect(result.current.uploaded).toBeNull();
    expect(result.current.usingStoredDocument).toBe(false);
    expect(result.current.file).toBeNull();
  });

  it('reports a getDocument failure and leaves the form untouched', async () => {
    const { result } = await renderEmpty();
    act(() => result.current.setTitle('Typed by hand'));
    vi.spyOn(documentsApi, 'getDocument').mockRejectedValue(new Error('boom'));

    await act(async () => {
      await result.current.preloadFromRun(historyItem());
    });

    expect(result.current.preloadError).toMatch(/boom|Unable to load/);
    expect(result.current.title).toBe('Typed by hand');
    expect(result.current.targetAgent).toBeNull();
    expect(result.current.uploaded).toBeNull();
  });

  it('keeps launch blocked for a FAILED stored document', async () => {
    const { result } = await renderEmpty();
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue({
      ...mockReadyDoc,
      processingStatus: 'FAILED',
      chunks: [],
    });
    await act(async () => {
      await result.current.preloadFromRun(historyItem());
    });
    await waitFor(() => expect(result.current.uploadedProcessingStatus).toBe('FAILED'));
    expect(result.current.uploadedDocumentReady).toBe(false);
    expect(result.current.canSubmitEvaluation).toBe(false);
  });

  it('refuses a run with no supported agent', async () => {
    const { result } = await renderEmpty();
    const getDoc = vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
    await act(async () => {
      await result.current.preloadFromRun(historyItem({ criterion_scores: [] }));
    });
    expect(getDoc).not.toHaveBeenCalled();
    expect(result.current.preloadError).toMatch(/agent/i);
    expect(result.current.uploaded).toBeNull();
  });
});

describe('preloadFromRun is non-destructive', () => {
  it('creates a new validation on the same document without mutating the original or calling update/delete APIs', async () => {
    mockCatalog();
    mockAdapters();
    const captured = captureSubmittedBody();
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);
    const spies = [
      ...Object.keys(documentsApi)
        .filter((k) => /^(update|delete|remove|patch)/i.test(k))
        .map((k) =>
          vi.spyOn(documentsApi as unknown as Record<string, () => unknown>, k).mockResolvedValue(undefined),
        ),
      ...Object.keys(modelValidationApi)
        .filter((k) => /^(update|delete|remove|patch)/i.test(k))
        .map((k) =>
          vi.spyOn(modelValidationApi as unknown as Record<string, () => unknown>, k).mockResolvedValue(undefined),
        ),
    ];
    const { result } = renderHook(() => useModelValidationFormState(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.criterionCatalog.isSuccess).toBe(true));

    const original = historyItem();
    const snapshot = JSON.parse(JSON.stringify(original));
    await act(async () => {
      await result.current.preloadFromRun(original);
    });
    await waitFor(() => expect(result.current.uploadedDocumentReady).toBe(true));
    await waitFor(() => expect(result.current.adapterChoices.isSuccess).toBe(true));
    act(() => {
      result.current.setExpectedScores({ 'sme:crit-sme-1': '1' });
      result.current.setModelChoice('base');
    });
    await act(async () => {
      result.current.handleStart();
    });

    expect(captured.body?.document_id).toBe(original.document_id);
    expect(captured.body?.expected_scores[0].expected_score).toBe(1);
    expect(original).toEqual(snapshot);
    expect(original.criterion_scores[0].expected_score).toBe(3);
    spies.forEach((spy) => expect(spy).not.toHaveBeenCalled());
  });
});
