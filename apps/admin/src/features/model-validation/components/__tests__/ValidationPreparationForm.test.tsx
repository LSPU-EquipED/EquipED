// @vitest-environment jsdom
import { useState } from 'react';
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
    registerScoreInput: vi.fn(),
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
    modelChoice: 'base',
    setModelChoice: vi.fn(),
    adapterOptions: [
      { value: 'base', label: 'Base model (no adapter)', disabled: false },
      { value: 'published', label: 'Published (v3)', disabled: false },
      { value: 'sme-v3', label: 'v3 ★ published · loaded', disabled: false },
      { value: 'sme-v4', label: 'v4 · not loaded', disabled: true },
    ],
    adapterChoices: {
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useModelValidationFormState>['adapterChoices'],
    targetAgent: 'sme',
    setTargetAgent: vi.fn(),
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
    expect(screen.getAllByText('2/2').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('1/1').length).toBeGreaterThanOrEqual(2);
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

    const reloadButton = screen.getByRole('button', {
      name: /Reload criteria catalog/i,
    });
    expect(reloadButton).toBeDefined();

    fireEvent.click(reloadButton);
    expect(handleReloadCatalog).toHaveBeenCalled();
  });

  it('renders Target then Model dropdowns, defaulting Model to the base model', () => {
    render(<ValidationPreparationForm form={createMockForm()} />);

    const target = screen.getByRole('button', { name: 'Target' });
    const model = screen.getByRole('button', { name: 'Model' });
    expect(target.textContent).toContain('SME only');
    expect(model.textContent).toContain('Base model');
    // Target comes before Model in the document.
    expect(
      target.compareDocumentPosition(model) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('offers SME, GAD and ITSO as targets, with no all-agents option', () => {
    render(<ValidationPreparationForm form={createMockForm()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Target' }));
    for (const name of [/SME only/, /GAD only/, /ITSO only/]) {
      expect((screen.getByRole('option', { name }) as HTMLButtonElement).disabled).toBe(false);
    }
    expect(screen.queryByRole('option', { name: /All agents/ })).toBeNull();
  });

  it('reports a Target change', () => {
    const setTargetAgent = vi.fn();
    render(<ValidationPreparationForm form={createMockForm({ setTargetAgent })} />);

    fireEvent.click(screen.getByRole('button', { name: 'Target' }));
    fireEvent.click(screen.getByRole('option', { name: /GAD only/ }));
    expect(setTargetAgent).toHaveBeenCalledWith('gad');
  });

  it('lists adapter options, disables not-loaded versions, and reports a version choice', () => {
    const setModelChoice = vi.fn();
    render(<ValidationPreparationForm form={createMockForm({ setModelChoice })} />);

    fireEvent.click(screen.getByRole('button', { name: 'Model' }));
    expect(screen.getByRole('option', { name: /Published \(v3\)/ })).toBeDefined();
    expect(screen.getByRole('option', { name: /v4/ }).getAttribute('aria-disabled')).toBe('true');

    fireEvent.click(screen.getByRole('option', { name: /^v3/ }));
    expect(setModelChoice).toHaveBeenCalledWith('sme-v3');
  });

  it('disables the Model dropdown with a prompt until an agent is chosen', () => {
    const form = createMockForm({
      targetAgent: null,
      criterionDefinitions: [],
      allCriterionScoresComplete: false,
    });
    render(<ValidationPreparationForm form={form} />);

    expect(screen.getByRole('button', { name: 'Target' }).textContent).toContain('Choose an agent');
    const model = screen.getByRole('button', { name: 'Model' }) as HTMLButtonElement;
    expect(model.textContent).toContain('Choose an agent first');
    expect(model.disabled).toBe(true);
  });

  it('shows a load hint when the chosen version is not loaded', () => {
    const form = createMockForm({
      modelChoice: 'sme-v4',
      adapterChoices: {
        data: {
          agent_id: 'sme',
          server_reachable: true,
          adapters: [
            { adapter_id: 'sme-v4', version: 4, loaded: false, published: false, gguf_filename: 'sme-v4.gguf' },
          ],
        },
      } as unknown as ReturnType<typeof useModelValidationFormState>['adapterChoices'],
    });
    render(<ValidationPreparationForm form={form} />);

    expect(screen.getByText(/Ask the host owner to load/)).toBeDefined();
    expect(screen.getByText('sme-v4.gguf')).toBeDefined();
  });

  it('does not render the removed partial-run acknowledgement', () => {
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
    });

    render(<ValidationPreparationForm form={form} />);

    expect(
      screen.queryByLabelText(/I understand that the Coordinator agent will be skipped/i),
    ).toBeNull();
  });

  it('activates the only in-scope agent tab even though the default tab state is SME', () => {
    const form = createMockForm({
      targetAgent: 'gad',
      criterionDefinitions: [mockAgents[1]],
    });

    render(<ValidationPreparationForm form={form} />);

    const gadTab = screen.getByRole('button', { name: /^GAD/ });
    expect(gadTab.className).toContain('bg-primary');
  });
});

describe('benchmark score editing', () => {
  it.each(['grouped', 'flat'])(
    'preserves score editing and keyboard handlers for %s catalogs',
    (shape) => {
      const form = createMockForm({
        criterionDefinitions: [
          { ...mockAgents[0], domains: shape === 'flat' ? [] : mockAgents[0].domains },
        ],
      });
      function ScoreEditor() {
        const [expectedScores, setExpectedScores] = useState(form.expectedScores);
        return <ValidationPreparationForm form={{ ...form, expectedScores, setExpectedScores }} />;
      }
      const { unmount } = render(<ScoreEditor />);
      const input = screen.getByLabelText(
        'Expected score for SME_1 Content accuracy',
      ) as HTMLInputElement;
      const otherInput = screen.getByLabelText(
        'Expected score for SME_2 Pedagogical structure',
      ) as HTMLInputElement;

      fireEvent.change(input, { target: { value: '2' } });
      expect(input.value).toBe('2');
      expect(otherInput.value).toBe('3');
      fireEvent.change(input, { target: { value: '5' } });
      expect(input.value).toBe('2');
      fireEvent.change(input, { target: { value: '' } });
      expect(input.value).toBe('');
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(form.handleScoreKeyDown).toHaveBeenCalledWith(expect.anything(), 'sme:crit-sme-1');
      expect(form.registerScoreInput).toHaveBeenCalledWith('sme:crit-sme-1', input);
      unmount();
      expect(form.registerScoreInput).toHaveBeenCalledWith('sme:crit-sme-1', null);
    },
  );
});
