// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvaluationSetup } from '../EvaluationSetup';
import { documentsApi } from '@/shared/api/documents.api';
import type { ClientDocument, CurriculumSuggestionResponse } from '@/shared/types/documents';

vi.mock('@/shared/api/documents.api', () => ({
  documentsApi: {
    getCurriculumSuggestion: vi.fn(),
  },
}));

const mockDoc: ClientDocument = {
  documentId: 'doc-slm-001',
  title: 'Data Structures SLM',
  courseTitle: 'Data Structures',
  lessonTitle: 'Module 1 - Arrays and Lists',
  academicYear: '2025-2026',
  courseCode: 'CS101',
  pageCount: 15,
  hasOcrPages: false,
  chunks: [],
  program: 'BSCS',
  sourceType: 'slm',
  uploadedAt: '2026-08-20T10:00:00Z',
  processingStatus: 'PROCESSED',
};

const mockCurriculaData: CurriculumSuggestionResponse = {
  documentId: 'doc-slm-001',
  detectedProgram: 'BSCS',
  selectedProgram: 'BSCS',
  detectedCourseCode: 'CS101',
  detectedAcademicYear: '2025-2026',
  detectedLessonTitle: 'Module 1 - Arrays and Lists',
  preferredSuggestion: {
    documentId: 'curr-ready-1',
    title: 'BSCS 2024 Revised Curriculum',
    program: 'BSCS',
    embeddingReady: true,
    matchReason: 'selected_program',
  },
  curriculumSuggestions: [
    {
      documentId: 'curr-ready-1',
      title: 'BSCS 2024 Revised Curriculum',
      program: 'BSCS',
      embeddingReady: true,
      matchReason: 'selected_program',
    },
    {
      documentId: 'curr-ready-2',
      title: 'BSCS 2022 Curriculum',
      program: 'BSCS',
      embeddingReady: true,
      matchReason: 'selected_program',
    },
  ],
  unavailableCurricula: [
    {
      documentId: 'curr-unavail-1',
      title: 'BSCS Legacy Draft Curriculum',
      program: 'BSCS',
      embeddingReady: false,
      matchReason: 'selected_program',
    },
  ],
};

function renderSetup(props: Partial<React.ComponentProps<typeof EvaluationSetup>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const defaultProps: React.ComponentProps<typeof EvaluationSetup> = {
    document: mockDoc,
    isLoadingDocument: false,
    documentError: null,
    selectedProgram: 'BSCS',
    detectedProgram: 'BSCS',
    onSelectProgram: vi.fn(),
    isResolveError: false,
    resolveError: null,
    onRetryResolve: vi.fn(),
    isSubmitting: false,
    submitError: null,
    onSubmit: vi.fn(),
    onRetrySubmit: vi.fn(),
    ...props,
  };

  const utils = render(
    <QueryClientProvider client={queryClient}>
      <EvaluationSetup {...defaultProps} />
    </QueryClientProvider>,
  );

  return { ...utils, queryClient, defaultProps };
}

describe('EvaluationSetup - Phase 2 Faculty Optional-Full Workflow', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.mocked(documentsApi.getCurriculumSuggestion).mockReset();
    vi.mocked(documentsApi.getCurriculumSuggestion).mockResolvedValue(mockCurriculaData);
  });

  it('renders semantic fieldsets, legends, labels, and metadata', () => {
    renderSetup();

    expect(screen.getByRole('heading', { name: 'Evaluation Setup' })).toBeDefined();
    expect(screen.getByText('Detected from SLM')).toBeDefined();
    expect(screen.getByText('CS101')).toBeDefined();
    expect(screen.getByText('Module 1 - Arrays and Lists')).toBeDefined();

    // Mode selection fieldset
    const modeLegend = screen.getByText('Select Evaluation Mode');
    expect(modeLegend).toBeDefined();
    expect(modeLegend.tagName.toLowerCase()).toBe('legend');

    // Confirm program checkbox
    const programCheckbox = screen.getByRole('checkbox', {
      name: /I confirm this SLM belongs to the selected program/i,
    }) as HTMLInputElement;
    expect(programCheckbox).toBeDefined();
    expect(programCheckbox.checked).toBe(false);

    // Start button is initially disabled
    const startButton = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startButton.disabled).toBe(true);
  });

  it('handles Full evaluation flow: requires program confirm + explicit curriculum selection with NO auto-selection, and posts exact payload', async () => {
    const onSubmit = vi.fn();
    renderSetup({ onSubmit });

    // 1. Confirm program
    const programCheckbox = screen.getByRole('checkbox', {
      name: /I confirm this SLM belongs to the selected program/i,
    }) as HTMLInputElement;
    fireEvent.click(programCheckbox);
    expect(programCheckbox.checked).toBe(true);

    // 2. Select Full Evaluation mode
    const fullModeRadio = screen.getByRole('radio', { name: /Full Evaluation/i }) as HTMLInputElement;
    fireEvent.click(fullModeRadio);
    expect(fullModeRadio.checked).toBe(true);

    // Curriculum suggestions fieldset appears
    await waitFor(() => {
      expect(screen.getByText('Select Curriculum Reference')).toBeDefined();
      expect(screen.getByText('BSCS 2024 Revised Curriculum')).toBeDefined();
      expect(screen.getByText('BSCS 2022 Curriculum')).toBeDefined();
    });

    // 3. NO AUTO-SELECTION: Verify ready radio inputs exist and none is checked by default (even though preferredSuggestion was in response)
    const radio1 = screen.getByRole('radio', { name: /BSCS 2024 Revised Curriculum/i }) as HTMLInputElement;
    const radio2 = screen.getByRole('radio', { name: /BSCS 2022 Curriculum/i }) as HTMLInputElement;
    expect(radio1.checked).toBe(false);
    expect(radio2.checked).toBe(false);

    // Start button remains disabled until curriculum is explicitly clicked
    const startButton = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startButton.disabled).toBe(true);

    // 4. Unavailable curricula are visible, disabled, and have accessible names
    expect(screen.getByText('BSCS Legacy Draft Curriculum')).toBeDefined();
    const unavailableRadio = screen.getByRole('radio', {
      name: /Unavailable curriculum: BSCS Legacy Draft Curriculum/i,
    }) as HTMLInputElement;
    expect(unavailableRadio).toBeDefined();
    expect(unavailableRadio.disabled).toBe(true);
    expect(document.querySelector('label[for="unavailable-curriculum-curr-unavail-1"]')).toBeDefined();

    // 5. Select curriculum 1
    fireEvent.click(radio1);
    expect(radio1.checked).toBe(true);
    expect(startButton.disabled).toBe(false);

    // 6. Submit full evaluation
    fireEvent.click(startButton);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      program: 'BSCS',
      mode: 'full',
      curriculumId: 'curr-ready-1',
    });
  });

  it('handles Partial evaluation flow: conditional acknowledgement appears only after partial is chosen, and posts exact payload', async () => {
    const onSubmit = vi.fn();
    renderSetup({ onSubmit });

    // 1. Confirm program
    const programCheckbox = screen.getByRole('checkbox', {
      name: /I confirm this SLM belongs to the selected program/i,
    }) as HTMLInputElement;
    fireEvent.click(programCheckbox);

    // Acknowledgement checkbox is NOT present before partial mode is selected
    expect(
      screen.queryByRole('checkbox', {
        name: /I understand that the Program Coordinator review will be skipped/i,
      }),
    ).toBeNull();

    // 2. Select Partial Evaluation mode
    const partialModeRadio = screen.getByRole('radio', { name: /Partial Evaluation/i }) as HTMLInputElement;
    fireEvent.click(partialModeRadio);
    expect(partialModeRadio.checked).toBe(true);

    // 3. Conditional acknowledgement checkbox is now visible but unchecked
    const ackCheckbox = screen.getByRole('checkbox', {
      name: /I understand that the Program Coordinator review will be skipped/i,
    }) as HTMLInputElement;
    expect(ackCheckbox).toBeDefined();
    expect(ackCheckbox.checked).toBe(false);

    const startButton = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startButton.disabled).toBe(true);

    // 4. Check acknowledgement
    fireEvent.click(ackCheckbox);
    expect(ackCheckbox.checked).toBe(true);
    expect(startButton.disabled).toBe(false);

    // 5. Submit partial evaluation
    fireEvent.click(startButton);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      program: 'BSCS',
      mode: 'partial',
      curriculumId: undefined,
    });
  });

  it('changing program emits exact canonical constant BSInfoTech and resets mode, curriculum selection, and acknowledgement', async () => {
    const onSelectProgram = vi.fn();
    const { rerender, queryClient } = renderSetup({
      selectedProgram: 'BSCS',
      onSelectProgram,
    });

    // Confirm program and set Full mode with selected curriculum
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I confirm this SLM belongs to the selected program/i,
      }),
    );
    fireEvent.click(screen.getByRole('radio', { name: /Full Evaluation/i }));

    await waitFor(() => {
      expect(screen.getByRole('radio', { name: /BSCS 2024 Revised Curriculum/i })).toBeDefined();
    });

    const radio1 = screen.getByRole('radio', { name: /BSCS 2024 Revised Curriculum/i }) as HTMLInputElement;
    fireEvent.click(radio1);
    expect(radio1.checked).toBe(true);

    // Mock new suggestions for BSInfoTech
    const bsitCurriculaData: CurriculumSuggestionResponse = {
      ...mockCurriculaData,
      selectedProgram: 'BSInfoTech',
      curriculumSuggestions: [
        {
          documentId: 'curr-bsit-1',
          title: 'BSIT 2024 Curriculum',
          program: 'BSInfoTech',
          embeddingReady: true,
          matchReason: 'selected_program',
        },
      ],
      unavailableCurricula: [],
    };
    vi.mocked(documentsApi.getCurriculumSuggestion).mockResolvedValueOnce(bsitCurriculaData);

    // Open ProgramSelector dropdown and choose BSInfoTech
    const programTrigger = screen.getByRole('button', { name: /Academic Program/i });
    fireEvent.click(programTrigger);

    const bsitOption = screen.getByRole('option', { name: /BSInfoTech/i });
    fireEvent.click(bsitOption);
    // Verifies canonical constant emitted without uppercase distortion
    expect(onSelectProgram).toHaveBeenCalledWith('BSInfoTech');

    // Rerender with the updated program prop
    rerender(
      <QueryClientProvider client={queryClient}>
        <EvaluationSetup
          document={mockDoc}
          isLoadingDocument={false}
          documentError={null}
          selectedProgram="BSInfoTech"
          detectedProgram="BSCS"
          onSelectProgram={onSelectProgram}
          isResolveError={false}
          resolveError={null}
          isSubmitting={false}
          submitError={null}
          onSubmit={vi.fn()}
          onRetrySubmit={vi.fn()}
        />
      </QueryClientProvider>,
    );

    // Program checkbox should be unchecked (reset)
    const resetProgramCheckbox = screen.getByRole('checkbox', {
      name: /I confirm this SLM belongs to the selected program/i,
    }) as HTMLInputElement;
    expect(resetProgramCheckbox.checked).toBe(false);

    // Evaluation mode radios should be reset / unselected
    const fullRadio = screen.getByRole('radio', { name: /Full Evaluation/i }) as HTMLInputElement;
    const partialRadio = screen.getByRole('radio', { name: /Partial Evaluation/i }) as HTMLInputElement;
    expect(fullRadio.checked).toBe(false);
    expect(partialRadio.checked).toBe(false);

    // Start button should be disabled
    const startBtn = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(true);
  });

  it('clears curriculum selection and disables submission when settled refresh removes/moves selected ID (ready -> unavailable transition)', async () => {
    const { queryClient, rerender } = renderSetup({
      selectedProgram: 'BSCS',
    });

    // 1. Confirm program and choose Full mode
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I confirm this SLM belongs to the selected program/i,
      }),
    );
    fireEvent.click(screen.getByRole('radio', { name: /Full Evaluation/i }));

    await waitFor(() => {
      expect(screen.getByRole('radio', { name: /BSCS 2024 Revised Curriculum/i })).toBeDefined();
    });

    // 2. Select curr-ready-1
    const radio1 = screen.getByRole('radio', { name: /BSCS 2024 Revised Curriculum/i }) as HTMLInputElement;
    fireEvent.click(radio1);
    expect(radio1.checked).toBe(true);

    const startBtn = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(false);

    // 3. Mock a settled refresh where curr-ready-1 became unavailable (admin retired/unindexed it)
    const refreshedCurriculaData: CurriculumSuggestionResponse = {
      ...mockCurriculaData,
      curriculumSuggestions: [
        {
          documentId: 'curr-ready-2',
          title: 'BSCS 2022 Curriculum',
          program: 'BSCS',
          embeddingReady: true,
          matchReason: 'selected_program',
        },
      ],
      unavailableCurricula: [
        {
          documentId: 'curr-ready-1',
          title: 'BSCS 2024 Revised Curriculum',
          program: 'BSCS',
          embeddingReady: false,
          matchReason: 'selected_program',
        },
      ],
    };

    queryClient.setQueryData(['curriculum-suggestion', 'doc-slm-001', 'BSCS'], refreshedCurriculaData);

    // Rerender component to receive updated query cache
    rerender(
      <QueryClientProvider client={queryClient}>
        <EvaluationSetup
          document={mockDoc}
          isLoadingDocument={false}
          documentError={null}
          selectedProgram="BSCS"
          detectedProgram="BSCS"
          onSelectProgram={vi.fn()}
          isResolveError={false}
          resolveError={null}
          isSubmitting={false}
          submitError={null}
          onSubmit={vi.fn()}
          onRetrySubmit={vi.fn()}
        />
      </QueryClientProvider>,
    );

    // 4. Verify selection was cleared and start button is disabled
    await waitFor(() => {
      expect(startBtn.disabled).toBe(true);
    });

    const radio2 = screen.getByRole('radio', { name: /BSCS 2022 Curriculum/i }) as HTMLInputElement;
    expect(radio2.checked).toBe(false);
  });

  it('existing-evaluation resolver failure blocks fresh submission and renders retry-only alert', () => {
    const onRetryResolve = vi.fn();
    renderSetup({
      isResolveError: true,
      resolveError: new Error('Database connection failed while resolving evaluations'),
      onRetryResolve,
    });

    // An alert role communicates the resolver failure
    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain('Unable to verify existing evaluations');
    expect(alert.textContent).toContain('Database connection failed while resolving evaluations');

    // Retry Check button is available
    const retryCheckBtn = screen.getByRole('button', { name: /Retry Check/i });
    fireEvent.click(retryCheckBtn);
    expect(onRetryResolve).toHaveBeenCalledTimes(1);

    // Mode selection and Start Evaluation are NOT rendered
    expect(screen.queryByText('Select Evaluation Mode')).toBeNull();
    expect(screen.queryByRole('button', { name: /Start Evaluation/i })).toBeNull();
  });

  it('displays loading state with role="status" and disables start button', async () => {
    // Return an unresolved promise to keep loading
    vi.mocked(documentsApi.getCurriculumSuggestion).mockImplementation(
      () => new Promise(() => {}),
    );

    renderSetup();

    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I confirm this SLM belongs to the selected program/i,
      }),
    );
    fireEvent.click(screen.getByRole('radio', { name: /Full Evaluation/i }));

    const statusElement = screen.getByRole('status');
    expect(statusElement).toBeDefined();
    expect(statusElement.textContent).toContain('Loading curriculum references for BSCS');

    const startBtn = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(true);
  });

  it('displays error state with role="alert", provides retry button, and disables start button', async () => {
    vi.mocked(documentsApi.getCurriculumSuggestion).mockRejectedValueOnce(
      new Error('Curriculum database unavailable'),
    );

    renderSetup();

    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I confirm this SLM belongs to the selected program/i,
      }),
    );
    fireEvent.click(screen.getByRole('radio', { name: /Full Evaluation/i }));

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toBeDefined();
      expect(alert.textContent).toContain('Unable to load curriculum suggestions');
      expect(alert.textContent).toContain('Curriculum database unavailable');
    });

    const retryButton = screen.getByRole('button', { name: /Retry/i });
    expect(retryButton).toBeDefined();

    const startBtn = screen.getByRole('button', { name: /Start Evaluation/i }) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(true);
  });

  it('renders submit error alert and calls onRetrySubmit when retry clicked', () => {
    const onRetrySubmit = vi.fn();
    renderSetup({
      submitError: new Error('Submission rate limit exceeded'),
      onRetrySubmit,
    });

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain('Submission rate limit exceeded');

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);
    expect(onRetrySubmit).toHaveBeenCalledTimes(1);
  });

  it('gates curriculum suggestions query until program is confirmed and full mode is selected', async () => {
    vi.mocked(documentsApi.getCurriculumSuggestion).mockClear();

    renderSetup();

    // Initially unconfirmed - query must not run
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();

    // Confirm program
    const programCheckbox = screen.getByRole('checkbox', {
      name: /I confirm this SLM belongs to the selected program/i,
    });
    fireEvent.click(programCheckbox);
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();

    // Select Partial mode - query must still not run
    const partialRadio = screen.getByRole('radio', { name: /Partial Evaluation/i });
    fireEvent.click(partialRadio);
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();

    // Select Full mode - query must run now
    const fullRadio = screen.getByRole('radio', { name: /Full Evaluation/i });
    fireEvent.click(fullRadio);

    await waitFor(() => {
      expect(documentsApi.getCurriculumSuggestion).toHaveBeenCalledTimes(1);
      expect(documentsApi.getCurriculumSuggestion).toHaveBeenCalledWith('doc-slm-001', 'BSCS');
    });
  });
});
