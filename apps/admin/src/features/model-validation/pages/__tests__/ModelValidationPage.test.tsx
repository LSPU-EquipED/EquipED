// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import React from 'react';
import { ModelValidationPage } from '../ModelValidationPage';
import * as queriesModule from '../../hooks/useModelValidationQueries';
import type { ModelValidationListResponse, ModelValidationMetricsResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    children,
    className,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

const mockHistoryData: ModelValidationListResponse = {
  items: [
    {
      validation_id: 'val-1',
      evaluation_id: 'eval-1',
      document_id: 'doc-1',
      document_title: 'Algorithms SLM',
      model_variant: null,
      compare_group_id: null,
      status: 'COMPLETED',
      criterion_scores: [],
      bound_forms: [],
      partial_without_curriculum: false,
      error_message: null,
      created_at: '2026-09-01T10:00:00Z',
      absolute_error: 0.25,
      latency_seconds: 3.2,
      score_perplexity: 1.1,
      toxicity_score: 0.0,
      toxicity_label: 'Clean',
      toxicity_explanation: 'No toxic comments',
      toxicity_error: null,
      toxicity_model: 'llama-guard-3',
    },
  ],
  total: 1,
};

const mockMetricsData: ModelValidationMetricsResponse = {
  completed_runs: 1,
  mean_absolute_error: 0.25,
  mean_latency_seconds: 3.2,
  score_perplexity: 1.1,
  mean_toxicity_score: 0.0,
  class_labels: ['1', '2', '3', '4'],
  confusion_matrix: [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ],
  agent_confusion_matrices: {},
};

describe('ModelValidationPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <ModelValidationPage />
      </QueryClientProvider>,
    );
  }

  it('defaults to the History tab and its associated panel', () => {
    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: mockHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();

    expect(screen.getByRole('tablist', { name: 'Validation workspace' })).toBeDefined();
    expect(screen.getByRole('tab', { name: 'History', selected: true })).toBeDefined();
    expect(screen.getByRole('tabpanel', { name: 'History' })).toBeDefined();
    expect(screen.getByText('Run history')).toBeDefined();
    expect(screen.getByText('Algorithms SLM')).toBeDefined();
  });

  it('switches between workspaces from the tabs', () => {
    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: mockHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();

    fireEvent.click(screen.getByRole('tab', { name: 'Analytics' }));

    expect(screen.getByText('Score confusion matrix')).toBeDefined();
    expect(screen.queryByText('Agreement analytics')).toBeNull();

    fireEvent.click(screen.getByRole('tab', { name: 'New benchmark' }));

    expect(screen.getByText('Prepare a benchmark run')).toBeDefined();
  });

  it('supports keyboard navigation with wrapping and Home and End keys', () => {
    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: mockHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();

    const historyTab = screen.getByRole('tab', { name: 'History' });
    const analyticsTab = screen.getByRole('tab', { name: 'Analytics' });
    const benchmarkTab = screen.getByRole('tab', { name: 'New benchmark' });

    for (const [from, key, to] of [
      [historyTab, 'ArrowRight', analyticsTab],
      [analyticsTab, 'End', benchmarkTab],
      [benchmarkTab, 'ArrowRight', historyTab],
      [historyTab, 'ArrowLeft', benchmarkTab],
      [benchmarkTab, 'Home', historyTab],
    ] as const) {
      fireEvent.keyDown(from, { key });
      expect(document.activeElement).toBe(to);
      expect(to.getAttribute('aria-selected')).toBe('true');
      expect(to.tabIndex).toBe(0);
      expect(from.tabIndex).toBe(-1);
      expect(screen.getByRole('tabpanel').id).toBe(to.getAttribute('aria-controls'));
    }
    expect(screen.queryByRole('tab', { name: /Compare/i })).toBeNull();
  });

  it('shows the Model and Target controls and in-flight progress under New Benchmark Run', () => {
    const inFlightHistoryData: ModelValidationListResponse = {
      items: [
        {
          ...mockHistoryData.items[0],
          validation_id: 'val-2',
          status: 'EVALUATING',
        },
      ],
      total: 1,
    };

    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: inFlightHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);

    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);

    renderPage();
    fireEvent.click(screen.getByRole('tab', { name: 'New benchmark' }));

    expect(screen.getByLabelText('Model')).toBeDefined();
    expect(screen.getByLabelText('Target')).toBeDefined();
    expect(screen.getByLabelText(/Agent progress for/i)).toBeDefined();
  });

  it('opens the selected run review and linked evaluation, then closes it by button or Escape', () => {
    vi.spyOn(queriesModule, 'useModelValidationHistory').mockReturnValue({
      data: mockHistoryData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationListResponse>);
    vi.spyOn(queriesModule, 'useModelValidationMetrics').mockReturnValue({
      data: mockMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<ModelValidationMetricsResponse>);
    vi.spyOn(queriesModule, 'useModelValidationDetail').mockReturnValue({
      data: mockHistoryData.items[0],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof queriesModule.useModelValidationDetail>);
    vi.spyOn(queriesModule, 'useModelValidationEvaluation').mockReturnValue({
      data: {
        evaluation_id: 'eval-1',
        status: 'COMPLETED',
        submitted_at: '2026-09-01T10:00:00Z',
        completed_at: '2026-09-01T10:00:03Z',
        duration_seconds: 3.2,
        partial_without_curriculum: false,
        partial_reason: null,
        error_message: null,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof queriesModule.useModelValidationEvaluation>);
    renderPage();

    const openReview = () =>
      fireEvent.click(screen.getByRole('button', { name: 'Open evaluation for Algorithms SLM' }));
    openReview();
    expect(
      screen.getByRole('region', { name: 'Validation details for Algorithms SLM' }),
    ).toBeDefined();
    expect(screen.getByText('eval-1')).toBeDefined();
    expect(screen.getByText('3.20 s')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Close validation details' }));
    expect(
      screen.queryByRole('region', { name: 'Validation details for Algorithms SLM' }),
    ).toBeNull();

    openReview();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(
      screen.queryByRole('region', { name: 'Validation details for Algorithms SLM' }),
    ).toBeNull();
  });
});
