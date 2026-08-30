// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { RubricTableEditor } from '../RubricTableEditor';
import type { RubricRevisionsResponse, RubricSet } from '../../types';

const mockSmeDraft: RubricSet = {
  rubric_set_id: 'set-sme-draft',
  agent_id: 'sme',
  name: 'SME Form Draft',
  version_number: 2,
  status: 'draft',
  domains: [
    {
      rubric_domain_id: 'dom-op',
      code: 'OP',
      title: 'Organization & Presentation',
      display_order: 1,
      criteria: [
        {
          rubric_criterion_id: 'crit-op1',
          criterion_code: 'OP-01',
          title: 'Topic Coherence',
          description: 'Topics are coherent from Unit to Chapter.',
          scoring_rule: '0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.',
          scoring_strategy: 'ratio_band',
          strategy_config: {
            strategy: 'ratio_band',
            mode: 'coverage_percentage',
            threshold_4: 90.0,
            threshold_3: 75.0,
            threshold_2: 60.0,
            short_sample: {
              min_units: 3,
              max_issues_4: 0,
              max_issues_3: 1,
              max_issues_2: 2,
            },
          },
          display_order: 1,
        },
        {
          rubric_criterion_id: 'crit-op2',
          criterion_code: 'OP-02',
          title: 'Language Clarity',
          description: 'Language is precise and age-appropriate.',
          scoring_rule: null,
          scoring_strategy: 'llm_rubric_guidance',
          strategy_config: {
            strategy: 'llm_rubric_guidance',
            guidance: 'Evaluate clear academic tone.',
          },
          display_order: 2,
        },
      ],
    },
    {
      rubric_domain_id: 'dom-as',
      code: 'AS',
      title: 'Assessment',
      display_order: 2,
      criteria: [
        {
          rubric_criterion_id: 'crit-as1',
          criterion_code: 'AS-01',
          title: 'Formative Exercises',
          description: 'Includes self-assessment exercises.',
          scoring_rule: 'Minimum 3 exercises for 4.',
          scoring_strategy: 'count_band',
          strategy_config: {
            strategy: 'count_band',
            mode: 'minimum_count',
            threshold_4: 3,
            threshold_3: 2,
            threshold_2: 1,
          },
          display_order: 1,
        },
      ],
    },
  ],
};

const mockSmePublished: RubricSet = {
  rubric_set_id: 'set-sme-pub-1',
  agent_id: 'sme',
  name: 'SME Form v1',
  version_number: 1,
  status: 'published',
  domains: [
    {
      rubric_domain_id: 'dom-op-pub',
      code: 'OP',
      title: 'Organization & Presentation',
      display_order: 1,
      criteria: [
        {
          rubric_criterion_id: 'crit-op1-pub',
          criterion_code: 'OP-01',
          title: 'Topic Coherence',
          description: 'Topics are coherent.',
          scoring_rule: '0 issues -> 4',
          scoring_strategy: 'ratio_band',
          strategy_config: {
            strategy: 'ratio_band',
            mode: 'coverage_percentage',
            threshold_4: 90.0,
            threshold_3: 75.0,
            threshold_2: 60.0,
          },
          display_order: 1,
        },
      ],
    },
  ],
};

const mockRevisionsData: RubricRevisionsResponse = {
  revisions: [mockSmeDraft, mockSmePublished],
  active_pointers: {
    sme: 'set-sme-pub-1',
    coordinator: 'set-coord-1',
    gad: 'set-gad-1',
    itso: 'set-itso-1',
  },
};

const createDraftMutateAsync = vi.fn();
const deleteDraftMutateAsync = vi.fn();
const validateDraftMutateAsync = vi.fn();
const publishRevisionMutateAsync = vi.fn();
const activateRevisionMutateAsync = vi.fn();
const retireRevisionMutateAsync = vi.fn();
const reorderTreeMutate = vi.fn();
const deleteDomainMutate = vi.fn();
const deleteCriterionMutate = vi.fn();

vi.mock('../../hooks/useRubrics', () => ({
  useRubricRevisions: () => ({
    data: mockRevisionsData,
    isLoading: false,
    isError: false,
    error: null,
  }),
  useCreateDraft: () => ({ mutateAsync: createDraftMutateAsync, isPending: false, error: null }),
  useDeleteDraft: () => ({ mutateAsync: deleteDraftMutateAsync, isPending: false, error: null }),
  useValidateDraft: () => ({
    mutateAsync: validateDraftMutateAsync,
    isPending: false,
    error: null,
  }),
  usePublishRevision: () => ({
    mutateAsync: publishRevisionMutateAsync,
    isPending: false,
    error: null,
  }),
  useActivateRevision: () => ({
    mutateAsync: activateRevisionMutateAsync,
    isPending: false,
    error: null,
  }),
  useRetireRevision: () => ({
    mutateAsync: retireRevisionMutateAsync,
    isPending: false,
    error: null,
  }),
  useReorderRubricTree: () => ({ mutate: reorderTreeMutate, isPending: false, error: null }),
  useCreateDomain: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useUpdateDomain: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useDeleteDomain: () => ({ mutate: deleteDomainMutate, isPending: false, error: null }),
  useCreateCriterion: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useUpdateCriterion: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useMoveCriterion: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }),
  useDeleteCriterion: () => ({ mutate: deleteCriterionMutate, isPending: false, error: null }),
  getRubricOperationError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  getValidationReportFromError: () => null,
}));

describe('RubricTableEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(cleanup);

  it('renders agent tabs and displays draft revision by default when draft exists', () => {
    render(<RubricTableEditor />);

    expect(screen.getByRole('tab', { name: /subject matter expert/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /program coordinator/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /gad/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /itso/i })).toBeDefined();

    expect(screen.getByText('Draft (Editable)')).toBeDefined();
    expect(screen.getByDisplayValue('OP-01')).toBeDefined();
    expect(screen.getByDisplayValue('OP-02')).toBeDefined();
    expect(screen.getByDisplayValue('AS-01')).toBeDefined();
  });

  it('renders strategy badges and configuration summaries for criteria', () => {
    render(<RubricTableEditor />);

    expect(screen.getByText(/Ratio Band \(Coverage % \+ Short-sample\)/i)).toBeDefined();
    expect(screen.getByText('LLM Guidance')).toBeDefined();
    expect(screen.getByText(/Count Band \(Min Count\)/i)).toBeDefined();
  });

  it('submits atomic tree reorder when moving criteria up/down', () => {
    render(<RubricTableEditor />);

    // In OP domain, move OP-01 down
    const moveDownButtons = screen.getAllByRole('button', { name: /move op-01 criterion down/i });
    expect(moveDownButtons.length).toBeGreaterThan(0);
    fireEvent.click(moveDownButtons[0]);

    expect(reorderTreeMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        rubricSetId: 'set-sme-draft',
        body: {
          domains: [
            {
              rubric_domain_id: 'dom-op',
              criterion_ids: ['crit-op2', 'crit-op1'],
            },
            {
              rubric_domain_id: 'dom-as',
              criterion_ids: ['crit-as1'],
            },
          ],
        },
      }),
    );
  });

  it('submits atomic tree reorder when moving domains up/down', () => {
    render(<RubricTableEditor />);

    const moveDomainDown = screen.getByRole('button', { name: /move op domain down/i });
    fireEvent.click(moveDomainDown);

    expect(reorderTreeMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        rubricSetId: 'set-sme-draft',
        body: {
          domains: [
            {
              rubric_domain_id: 'dom-as',
              criterion_ids: ['crit-as1'],
            },
            {
              rubric_domain_id: 'dom-op',
              criterion_ids: ['crit-op1', 'crit-op2'],
            },
          ],
        },
      }),
    );
  });

  it('triggers draft validation and displays report', async () => {
    validateDraftMutateAsync.mockResolvedValueOnce({
      is_valid: true,
      issues: [],
      estimated_prompt_chars: 1250,
      criteria_count: 3,
    });

    render(<RubricTableEditor />);

    const validateBtn = screen.getByRole('button', { name: /validate/i });
    fireEvent.click(validateBtn);

    expect(validateDraftMutateAsync).toHaveBeenCalledWith('set-sme-draft');
    expect(await screen.findByText(/form conforms to agent capability manifest/i)).toBeDefined();
    expect(screen.getByText(/Criteria Count: 3/i)).toBeDefined();
  });

  it('opens publish modal and submits with activation flag', async () => {
    publishRevisionMutateAsync.mockResolvedValueOnce({
      ...mockSmeDraft,
      status: 'published',
      version_number: 2,
    });

    render(<RubricTableEditor />);

    fireEvent.click(screen.getByRole('button', { name: /publish revision/i }));
    expect(screen.getByRole('dialog', { name: /publish revision v2/i })).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: /publish and activate/i }));

    expect(publishRevisionMutateAsync).toHaveBeenCalledWith({
      rubricSetId: 'set-sme-draft',
      activate: true,
    });
  });
});
