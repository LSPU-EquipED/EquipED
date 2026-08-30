// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ValidationPreparationForm } from '../ValidationPreparationForm';
import type { useModelValidationFormState } from '../../hooks/useModelValidationFormState';
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
            title: 'Content accuracy',
            description: 'Check content accuracy',
            domain_title: 'Content Quality',
            display_order: 1,
          },
          {
            rubric_criterion_id: 'crit-sme-2',
            criterion_code: 'SME_2',
            criterion_id: 'crit-sme-2',
            title: 'Pedagogical structure',
            description: 'Check pedagogy',
            domain_title: 'Content Quality',
            display_order: 2,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-sme-1',
        criterion_code: 'SME_1',
        criterion_id: 'crit-sme-1',
        title: 'Content accuracy',
        description: 'Check content accuracy',
        domain_title: 'Content Quality',
        display_order: 1,
      },
      {
        rubric_criterion_id: 'crit-sme-2',
        criterion_code: 'SME_2',
        criterion_id: 'crit-sme-2',
        title: 'Pedagogical structure',
        description: 'Check pedagogy',
        domain_title: 'Content Quality',
        display_order: 2,
      },
    ],
  },
  {
    agent_id: 'gad',
    agent_name: 'GAD',
    rubric_set_id: 'set-gad-1',
    rubric_version: 2,
    domains: [
      {
        rubric_domain_id: 'dom-gad-1',
        code: 'GENDER',
        title: 'Gender Equality',
        display_order: 1,
        criteria: [
          {
            rubric_criterion_id: 'crit-gad-1',
            criterion_code: 'GAD_1',
            criterion_id: 'crit-gad-1',
            title: 'Gender sensitivity',
            description: 'Check gender sensitivity',
            domain_title: 'Gender Equality',
            display_order: 1,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-gad-1',
        criterion_code: 'GAD_1',
        criterion_id: 'crit-gad-1',
        title: 'Gender sensitivity',
        description: 'Check gender sensitivity',
        domain_title: 'Gender Equality',
        display_order: 1,
      },
    ],
  },
  {
    agent_id: 'itso',
    agent_name: 'ITSO',
    rubric_set_id: 'set-itso-1',
    rubric_version: 1,
    domains: [
      {
        rubric_domain_id: 'dom-itso-1',
        code: 'IP',
        title: 'Intellectual Property',
        display_order: 1,
        criteria: [
          {
            rubric_criterion_id: 'crit-itso-1',
            criterion_code: 'ITSO_1',
            criterion_id: 'crit-itso-1',
            title: 'IP compliance',
            description: 'Check IP compliance',
            domain_title: 'Intellectual Property',
            display_order: 1,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-itso-1',
        criterion_code: 'ITSO_1',
        criterion_id: 'crit-itso-1',
        title: 'IP compliance',
        description: 'Check IP compliance',
        domain_title: 'Intellectual Property',
        display_order: 1,
      },
    ],
  },
];

function createMockForm(overrides: Partial<ReturnType<typeof useModelValidationFormState>> = {}) {
  const defaultForm: ReturnType<typeof useModelValidationFormState> = {
    fileInputRef: { current: null },
    scoreInputRefs: { current: {} },
    file: null,
    title: 'Sample SLM',
    setTitle: vi.fn(),
    program: 'BSCS',
    expectedScores: {
      'sme:crit-sme-1': '4',
      'sme:crit-sme-2': '3',
      'gad:crit-gad-1': '4',
      'itso:crit-itso-1': '4',
    },
    setExpectedScores: vi.fn(),
    uploaded: null,
    partialChoiceAcknowledged: false,
    setPartialChoiceAcknowledged: vi.fn(),
    criterionCatalog: {
      data: { agents: mockAgents, total_criteria: 4 },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useModelValidationFormState>['criterionCatalog'],
    uploadMutation: {
      mutate: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useModelValidationFormState>['uploadMutation'],
    validationMutation: {
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useModelValidationFormState>['validationMutation'],
    criterionDefinitions: mockAgents,
    allCriterionScoresComplete: true,
    uploadedProcessingStatus: undefined,
    uploadedDocumentReady: false,
    canSubmitEvaluation: false,
    error: null,
    isStaleBinding: false,
    handleReloadCatalog: vi.fn(),
    normalizedProgram: 'BSCS',
    resetPreparedUpload: vi.fn(),
    handleFile: vi.fn(),
    handleProgramChange: vi.fn(),
    handlePrepare: vi.fn(),
    handleScoreKeyDown: vi.fn(),
    handleStart: vi.fn(),
  };

  return { ...defaultForm, ...overrides };
}

describe('ValidationPreparationForm', () => {
  it('renders active criteria carrying agent name, rubric version, domain order, and criterion code/title', () => {
    const form = createMockForm();
    render(<ValidationPreparationForm form={form} />);

    expect(screen.getByText('Subject Matter Expert')).toBeDefined();
    expect(screen.getAllByText('Rubric v1')).toHaveLength(2);
    expect(screen.getByText('CONTENT · Content Quality')).toBeDefined();
    expect(screen.getAllByText('Domain #1')).toHaveLength(3);
    expect(screen.getByText('SME_1 · Content accuracy')).toBeDefined();
    expect(screen.getByText('SME_2 · Pedagogical structure')).toBeDefined();

    expect(screen.getByText('GAD')).toBeDefined();
    expect(screen.getByText('Rubric v2')).toBeDefined();
    expect(screen.getByText('GENDER · Gender Equality')).toBeDefined();
    expect(screen.getByText('GAD_1 · Gender sensitivity')).toBeDefined();

    expect(screen.getByText('ITSO')).toBeDefined();
    expect(screen.getByText('IP · Intellectual Property')).toBeDefined();
    expect(screen.getByText('ITSO_1 · IP compliance')).toBeDefined();
  });

  it('renders score inputs with 1-4 placeholder, maxLength 1, and wheel prevention', () => {
    const form = createMockForm();
    render(<ValidationPreparationForm form={form} />);

    const smeInput = screen.getByLabelText(
      'Expected score for SME_1 Content accuracy',
    ) as HTMLInputElement;
    expect(smeInput).toBeDefined();
    expect(smeInput.maxLength).toBe(1);
    expect(smeInput.placeholder).toBe('1–4');

    // Trigger wheel event: should blur input
    const blurSpy = vi.spyOn(smeInput, 'blur');
    fireEvent.wheel(smeInput);
    expect(blurSpy).toHaveBeenCalled();
  });

  it('renders partial acknowledgement checkbox and triggers acknowledgement change', () => {
    const setPartialChoiceAcknowledged = vi.fn();
    const form = createMockForm({
      uploaded: {
        documentId: 'doc-1',
        title: 'SLM 1',
        sourceType: 'slm',
        processingStatus: 'PROCESSED',
        academicYear: null,
        courseCode: null,
        courseTitle: null,
        lessonTitle: null,
      },
      uploadedDocumentReady: true,
      partialChoiceAcknowledged: false,
      setPartialChoiceAcknowledged,
    });

    render(<ValidationPreparationForm form={form} />);

    const checkbox = screen.getByLabelText(
      /I understand that the Coordinator agent will be skipped/i,
    );
    expect(checkbox).toBeDefined();

    fireEvent.click(checkbox);
    expect(setPartialChoiceAcknowledged).toHaveBeenCalledWith(true);
  });

  it('displays clear stale binding error requiring catalog reload on 409/422', () => {
    const handleReloadCatalog = vi.fn();
    const form = createMockForm({
      isStaleBinding: true,
      handleReloadCatalog,
      validationMutation: {
        mutate: vi.fn(),
        reset: vi.fn(),
        isPending: false,
        error: new Error('Cross-revision criteria detected'),
      } as unknown as ReturnType<typeof useModelValidationFormState>['validationMutation'],
    });

    render(<ValidationPreparationForm form={form} />);

    expect(screen.getByText('Active rubric criteria have changed')).toBeDefined();
    expect(
      screen.getByText(/The published rubric revisions or criteria were updated or retired/i),
    ).toBeDefined();

    const reloadButton = screen.getByRole('button', { name: /Reload criteria catalog/i });
    expect(reloadButton).toBeDefined();

    fireEvent.click(reloadButton);
    expect(handleReloadCatalog).toHaveBeenCalled();
  });
});
