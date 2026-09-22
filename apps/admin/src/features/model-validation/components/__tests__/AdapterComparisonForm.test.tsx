// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { AdapterComparisonForm } from '../AdapterComparisonForm';
import type { AdapterComparisonFormState } from '../../hooks/useAdapterComparisonFormState';
import type { ModelValidationAgentCriteria } from '../../types';

afterEach(() => {
  cleanup();
});

const mockAgents: ModelValidationAgentCriteria[] = [
  {
    agent_id: 'sme',
    agent_name: 'Subject Matter Expert',
    rubric_set_id: 'set-sme-1',
    rubric_version: 1,
    domains: [],
    criteria: [
      {
        rubric_criterion_id: 'crit-sme-1',
        criterion_code: 'SME_1',
        criterion_id: 'crit-sme-1',
        title: 'Content accuracy',
        description: 'Check content accuracy',
        display_order: 1,
      },
    ],
  },
  {
    agent_id: 'gad',
    agent_name: 'GAD',
    rubric_set_id: 'set-gad-1',
    rubric_version: 2,
    domains: [],
    criteria: [
      {
        rubric_criterion_id: 'crit-gad-1',
        criterion_code: 'GAD_1',
        criterion_id: 'crit-gad-1',
        title: 'Gender sensitivity',
        description: 'Check gender sensitivity',
        display_order: 1,
      },
    ],
  },
  {
    agent_id: 'itso',
    agent_name: 'ITSO',
    rubric_set_id: 'set-itso-1',
    rubric_version: 1,
    domains: [],
    criteria: [
      {
        rubric_criterion_id: 'crit-itso-1',
        criterion_code: 'ITSO_1',
        criterion_id: 'crit-itso-1',
        title: 'IP compliance',
        description: 'Check IP compliance',
        display_order: 1,
      },
    ],
  },
];

function createMockForm(overrides: Partial<AdapterComparisonFormState> = {}): AdapterComparisonFormState {
  const defaultForm: AdapterComparisonFormState = {
    fileInputRef: { current: null },
    file: null,
    title: 'Sample SLM',
    setTitle: vi.fn(),
    program: 'BSCS',
    handleProgramChange: vi.fn(),
    selectedAgent: null,
    setSelectedAgent: vi.fn(),
    expectedScores: {},
    setExpectedScores: vi.fn(),
    uploaded: null,
    criterionCatalog: {
      data: { agents: mockAgents, total_criteria: 3 },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as AdapterComparisonFormState['criterionCatalog'],
    compareAgents: mockAgents,
    selectedAgentCriteria: [],
    uploadMutation: {
      mutate: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as AdapterComparisonFormState['uploadMutation'],
    compareMutation: {
      mutate: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as AdapterComparisonFormState['compareMutation'],
    allCriterionScoresComplete: false,
    uploadedProcessingStatus: undefined,
    uploadedDocumentReady: false,
    canSubmitEvaluation: false,
    error: null,
    handleFile: vi.fn(),
    handlePrepare: vi.fn(),
    handleStart: vi.fn(),
  };

  return { ...defaultForm, ...overrides };
}

describe('AdapterComparisonForm', () => {
  it('renders one button for each compare-eligible agent, excluding Coordinator', () => {
    const form = createMockForm();
    render(<AdapterComparisonForm form={form} />);

    expect(screen.getByRole('button', { name: 'Subject Matter Expert' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'GAD Evaluator' })).toBeDefined();
    expect(
      screen.getByRole('button', { name: 'Innovation and Technology Support Office' }),
    ).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Program Coordinator' })).toBeNull();
  });

  it('calls setSelectedAgent when an agent button is clicked', () => {
    const setSelectedAgent = vi.fn();
    const form = createMockForm({ setSelectedAgent });
    render(<AdapterComparisonForm form={form} />);

    fireEvent.click(screen.getByRole('button', { name: 'GAD Evaluator' }));
    expect(setSelectedAgent).toHaveBeenCalledWith('gad');
  });

  it('reveals the selected agent criteria inputs once an agent is chosen', () => {
    const form = createMockForm({
      selectedAgent: 'sme',
      selectedAgentCriteria: mockAgents[0].criteria,
    });
    render(<AdapterComparisonForm form={form} />);

    expect(screen.getByText('SME_1 · Content accuracy')).toBeDefined();
    expect(
      screen.getByLabelText('Expected score for SME_1 Content accuracy'),
    ).toBeDefined();
  });

  it('shows a prompt to choose a target agent before one is selected', () => {
    const form = createMockForm();
    render(<AdapterComparisonForm form={form} />);

    expect(screen.getByText('Choose a target agent above to enter its expected scores.')).toBeDefined();
  });

  it('disables the start-comparison button until canSubmitEvaluation is true', () => {
    const uploaded = {
      documentId: 'doc-1',
      title: 'SLM 1',
      sourceType: 'slm' as const,
      processingStatus: 'PROCESSED' as const,
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    };

    const { rerender } = render(
      <AdapterComparisonForm
        form={createMockForm({
          uploaded,
          uploadedDocumentReady: true,
          canSubmitEvaluation: false,
        })}
      />,
    );

    expect(
      screen.getByRole('button', { name: /Waiting for SLM…/i }),
    ).toHaveProperty('disabled', true);

    rerender(
      <AdapterComparisonForm
        form={createMockForm({
          uploaded,
          uploadedDocumentReady: true,
          canSubmitEvaluation: true,
        })}
      />,
    );

    expect(
      screen.getByRole('button', { name: /Start comparison/i }),
    ).toHaveProperty('disabled', false);
  });
});
