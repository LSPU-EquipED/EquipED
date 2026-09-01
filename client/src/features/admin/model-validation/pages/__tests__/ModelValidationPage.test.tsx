// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import React from 'react';
import { ModelValidationPage } from '../ModelValidationPage';
import * as queriesModule from '../../hooks/useModelValidationQueries';
import * as formStateModule from '../../hooks/useModelValidationFormState';
import type { ModelValidationListResponse, ModelValidationMetricsResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, className }: { to: string; children?: React.ReactNode; className?: string }) => (
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
      program: 'BSCS',
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
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
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

  it('renders workstation header and defaults to Validation History tab above the fold', () => {
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

    // Tabs navigation bar
    expect(screen.getByRole('tab', { name: /Validation History/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Confusion Matrix & Analytics/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /New Benchmark Run/i })).toBeDefined();
    // Default History tab content
    expect(screen.getByText('Completed Runs')).toBeDefined();
    expect(screen.getByText('Mean Absolute Error')).toBeDefined();
    expect(screen.getAllByText(/Validation History/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Algorithms SLM')).toBeDefined();
  });

  it('switches between tabs on click', () => {
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

    // Switch to Confusion Matrix & Analytics tab
    const analyticsTab = screen.getByRole('tab', { name: /Confusion Matrix & Analytics/i });
    fireEvent.click(analyticsTab);

    expect(screen.getByText('Score confusion matrix')).toBeDefined();

    // Switch to New Benchmark Run tab
    const newRunTab = screen.getByRole('tab', { name: /New Benchmark Run/i });
    fireEvent.click(newRunTab);

    expect(screen.getByText('New validation input')).toBeDefined();
  });
});
