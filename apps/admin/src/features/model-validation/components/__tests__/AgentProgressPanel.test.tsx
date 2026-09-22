// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach } from 'vitest';
import { AgentProgressPanel } from '../AgentProgressPanel';
import type { ModelValidationItem } from '../../types';

afterEach(() => {
  cleanup();
});

const baseItem: ModelValidationItem = {
  validation_id: 'val-1',
  evaluation_id: 'eval-1',
  document_id: 'doc-1',
  document_title: 'Sample SLM',
  model_variant: null,
  compare_group_id: null,
  partial_without_curriculum: false,
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
  status: 'EVALUATING',
  error_message: null,
  created_at: '2026-09-23T00:00:00Z',
};

describe('AgentProgressPanel', () => {
  it('renders exactly one agent card when criterion_scores all share one agent_id', () => {
    const item: ModelValidationItem = {
      ...baseItem,
      status: 'SYNTHESIZING',
      criterion_scores: [
        {
          expected_score_id: 'exp-1',
          agent_id: 'sme',
          rubric_set_id: 'set-sme-1',
          rubric_version: 1,
          rubric_criterion_id: 'crit-sme-1',
          criterion_id: 'SME_1',
          criterion_title: 'Content accuracy',
          expected_score: 4,
          actual_score: 4,
          absolute_error: 0,
        },
      ],
    };

    render(<AgentProgressPanel validation={item} />);

    expect(screen.getByText('Subject Matter Expert')).toBeDefined();
    expect(screen.queryByText('Program Coordinator')).toBeNull();
    expect(screen.queryByText('GAD Evaluator')).toBeNull();
    expect(
      screen.queryByText('Innovation and Technology Support Office'),
    ).toBeNull();
  });

  it('renders all four agent cards when no criterion_scores exist yet (regression guard)', () => {
    render(<AgentProgressPanel validation={baseItem} />);

    expect(screen.getByText('Subject Matter Expert')).toBeDefined();
    expect(screen.getByText('Program Coordinator')).toBeDefined();
    expect(screen.getByText('GAD Evaluator')).toBeDefined();
    expect(screen.getByText('Innovation and Technology Support Office')).toBeDefined();
  });
});
