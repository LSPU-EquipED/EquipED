// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvaluationConfirmModal } from '../EvaluationConfirmModal';
import { evaluationApi } from '../../api/evaluation.api';
import { documentsApi } from '@/shared/api/documents.api';
import type { CurriculumSuggestionResponse } from '@/shared/types/documents';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    submitEvaluation: vi.fn(),
    listEvaluations: vi.fn(),
    getEvaluation: vi.fn(),
    getEvaluationStatus: vi.fn(),
    getEvaluationResults: vi.fn(),
    submitCriterionFeedback: vi.fn(),
  },
}));

vi.mock('@/shared/api/documents.api', () => ({
  documentsApi: {
    getCurriculumSuggestion: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({}),
  useLocation: () => ({ search: '' }),
}));

const mockCurricula: CurriculumSuggestionResponse = {
  documentId: 'doc-1',
  detectedProgram: 'BSCS',
  selectedProgram: 'BSCS',
  detectedCourseCode: 'CS101',
  detectedAcademicYear: '2025-2026',
  detectedLessonTitle: 'Module 1',
  preferredSuggestion: {
    documentId: 'curr-1',
    title: 'BSCS 2024 Curriculum',
    program: 'BSCS',
    embeddingReady: true,
    matchReason: 'selected_program',
  },
  curriculumSuggestions: [
    {
      documentId: 'curr-1',
      title: 'BSCS 2024 Curriculum',
      program: 'BSCS',
      embeddingReady: true,
      matchReason: 'selected_program',
    },
  ],
  unavailableCurricula: [],
};

function renderModal(
  props: Partial<React.ComponentProps<typeof EvaluationConfirmModal>> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onClose = vi.fn();
  const onSubmitted = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <EvaluationConfirmModal
        documentId="doc-1"
        documentTitle="Data Structures SLM"
        detectedProgram="BSCS"
        targetAgent="gad"
        onClose={onClose}
        onSubmitted={onSubmitted}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onClose, onSubmitted };
}

describe('EvaluationConfirmModal', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.getCurriculumSuggestion).mockResolvedValue(mockCurricula);
    vi.mocked(evaluationApi.submitEvaluation).mockResolvedValue({
      evaluation_id: 'eval-1',
      document_id: 'doc-1',
      target_agent: 'gad',
      status: 'SUBMITTED',
      submitted_at: '2026-09-08T00:00:00Z',
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders document title, target role, and role requirement', () => {
    renderModal();
    expect(screen.getByText('Data Structures SLM')).toBeDefined();
    expect(screen.getByText('GAD Unit')).toBeDefined();
    expect(
      screen.getByText(/directly from the SLM text. No curriculum reference required/i),
    ).toBeDefined();
  });

  it('submits a GAD evaluation without curriculum context', async () => {
    const { onClose, onSubmitted } = renderModal({ targetAgent: 'gad' });

    fireEvent.click(screen.getByRole('button', { name: /Run GAD Evaluation/i }));

    await waitFor(() => expect(evaluationApi.submitEvaluation).toHaveBeenCalledTimes(1));
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: 'doc-1',
      target_agent: 'gad',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith('eval-1'));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(documentsApi.getCurriculumSuggestion).not.toHaveBeenCalled();
  });

  it('blocks coordinator submission until a curriculum reference is selected', async () => {
    renderModal({ targetAgent: 'coordinator' });

    expect(screen.getByText('Program Coordinator')).toBeDefined();
    const runButton = screen.getByRole('button', {
      name: /Run Coordinator Evaluation/i,
    }) as HTMLButtonElement;
    expect(runButton.disabled).toBe(true);

    await waitFor(() => {
      expect(screen.getByText('BSCS 2024 Curriculum')).toBeDefined();
    });
    fireEvent.click(screen.getByRole('radio', { name: /BSCS 2024 Curriculum/i }));
    expect(runButton.disabled).toBe(false);

    fireEvent.click(runButton);
    await waitFor(() => expect(evaluationApi.submitEvaluation).toHaveBeenCalledTimes(1));
    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: 'doc-1',
      curriculum_id: 'curr-1',
      target_agent: 'coordinator',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
  });

  it('closes on Escape', () => {
    const { onClose } = renderModal();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
