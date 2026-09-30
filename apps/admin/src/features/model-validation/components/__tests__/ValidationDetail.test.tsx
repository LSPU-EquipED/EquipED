// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ValidationDetail } from '../ValidationDetail';
import { ValidationHistoryRow } from '../ValidationHistoryRow';
import { ValidationReviewPanel } from '../ValidationReviewPanel';
import type { ModelValidationItem } from '../../types';

// Mock the queries used inside ValidationDetail
vi.mock('../../hooks/useModelValidationQueries', () => ({
  useModelValidationDetail: () => ({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  }),
  useModelValidationEvaluation: () => ({
    data: null,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

afterEach(() => {
  cleanup();
});

const mockItem: ModelValidationItem = {
  validation_id: 'val-uuid-1',
  evaluation_id: 'eval-uuid-1',
  document_id: 'doc-uuid-1',
  document_title: 'Introduction to Computing SLM',
  model_variant: null,
  adapter_id: null,
  adapter_label: null,
  adapter_resolution: null,
  compare_group_id: null,
  partial_without_curriculum: true,
  bound_forms: [
    {
      agent_id: 'sme',
      rubric_set_id: 'set-sme-1',
      rubric_version: 1,
      adapter_key: 'sme_guidance_adapter',
      adapter_version: 1,
    },
    {
      agent_id: 'gad',
      rubric_set_id: 'set-gad-1',
      rubric_version: 2,
      adapter_key: 'gad_score_adapter',
      adapter_version: 2,
    },
    {
      agent_id: 'itso',
      rubric_set_id: 'set-itso-1',
      rubric_version: 1,
      adapter_key: 'itso_guidance_adapter',
      adapter_version: 1,
    },
  ],
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
    {
      expected_score_id: 'exp-2',
      agent_id: 'gad',
      rubric_set_id: 'set-gad-1',
      rubric_version: 2,
      rubric_criterion_id: 'crit-gad-1',
      criterion_id: 'GAD_1',
      criterion_title: 'Gender sensitivity',
      expected_score: 3,
      actual_score: 2,
      absolute_error: 1,
    },
  ],
  absolute_error: 0.5,
  latency_seconds: 12.3,
  score_perplexity: 1.65,
  toxicity_score: 0.02,
  toxicity_label: 'Low',
  toxicity_explanation: 'No offensive language',
  toxicity_model: 'llama3',
  toxicity_error: null,
  status: 'COMPLETED',
  error_message: null,
  created_at: '2026-08-30T10:00:00Z',
};

describe('ValidationDetail', () => {
  it('renders bound rubric revisions panel with version, adapter, and rubric set id', () => {
    render(
      <ValidationDetail
        id="test-detail"
        validationId={mockItem.validation_id}
        fallbackCriteria={mockItem.criterion_scores}
        boundForms={mockItem.bound_forms}
        partialWithoutCurriculum={mockItem.partial_without_curriculum}
        overallStatus={mockItem.status}
        errorMessage={mockItem.error_message}
        isExpanded={true}
      />,
    );

    expect(screen.getByText('Bound rubric revisions')).toBeDefined();
    expect(
      screen.getByText(/Immutable form snapshots bound at validation admission/i),
    ).toBeDefined();
    expect(screen.getAllByText('Rubric v1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Rubric v2').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/sme_guidance_adapter \(v1\)/i)).toBeDefined();
    expect(screen.getByText(/gad_score_adapter \(v2\)/i)).toBeDefined();
    expect(screen.getByText('set-sme-1')).toBeDefined();
    expect(screen.getByText('set-gad-1')).toBeDefined();
  });

  it('renders Coordinator as skipped in partial evaluation without curriculum', () => {
    render(
      <ValidationDetail
        id="test-detail"
        validationId={mockItem.validation_id}
        fallbackCriteria={mockItem.criterion_scores}
        boundForms={mockItem.bound_forms}
        partialWithoutCurriculum={true}
        overallStatus={mockItem.status}
        errorMessage={null}
        isExpanded={true}
      />,
    );

    expect(screen.getByText(/This validation ran without a curriculum reference/i)).toBeDefined();
  });
});

describe('HistoryRow', () => {
  it('renders bound form revision badges under the document title', () => {
    render(
      <table>
        <tbody>
          <ValidationHistoryRow
            item={mockItem}
            isExpanded={false}
            comparedCount={2}
            exactMatches={1}
            onToggle={vi.fn()}
          />
        </tbody>
      </table>,
    );

    expect(screen.getByText('Introduction to Computing SLM')).toBeDefined();
    expect(screen.getByText('SME v1')).toBeDefined();
    expect(screen.getByText('GAD v2')).toBeDefined();
    expect(screen.getByText('ITSO v1')).toBeDefined();
  });

  it('shows an Adapter variant badge when model_variant is adapter', () => {
    render(
      <table>
        <tbody>
          <ValidationHistoryRow
            item={{ ...mockItem, model_variant: 'adapter' }}
            isExpanded={false}
            comparedCount={2}
            exactMatches={1}
            onToggle={vi.fn()}
          />
        </tbody>
      </table>,
    );

    expect(screen.getByText('Adapter')).toBeDefined();
  });

  it('shows no variant badge when model_variant is null', () => {
    render(
      <table>
        <tbody>
          <ValidationHistoryRow
            item={{ ...mockItem, model_variant: null }}
            isExpanded={false}
            comparedCount={2}
            exactMatches={1}
            onToggle={vi.fn()}
          />
        </tbody>
      </table>,
    );

    expect(screen.queryByText('Adapter')).toBeNull();
    expect(screen.queryByText('Base')).toBeNull();
  });
});

describe('adapter labelling', () => {
  function renderRow(item: ModelValidationItem) {
    render(
      <table>
        <tbody>
          <ValidationHistoryRow
            item={item}
            isExpanded={false}
            comparedCount={2}
            exactMatches={1}
            onToggle={vi.fn()}
          />
        </tbody>
      </table>,
    );
  }

  it('shows the adapter version label on a history row when present', () => {
    renderRow({ ...mockItem, model_variant: 'adapter', adapter_id: 'sme-v3', adapter_label: 'sme-v3' });

    expect(screen.getByText('Adapter sme-v3')).toBeDefined();
  });

  it('falls back to the plain Adapter text for old rows without a label', () => {
    renderRow({ ...mockItem, model_variant: 'adapter', adapter_label: null });

    expect(screen.getByText('Adapter')).toBeDefined();
  });

  it('shows the adapter version label in the review panel', () => {
    render(
      <ValidationReviewPanel
        item={{ ...mockItem, model_variant: 'adapter', adapter_id: 'sme-v3', adapter_label: 'sme-v3' }}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('Adapter sme-v3')).toBeDefined();
  });

  it('keeps the plain Base/Adapter text in the review panel for old rows', () => {
    render(
      <ValidationReviewPanel item={{ ...mockItem, model_variant: 'base' }} onClose={vi.fn()} />,
    );

    expect(screen.getByText('Base')).toBeDefined();
  });

  it('says base was used when an adapter was requested but not applied', () => {
    render(
      <ValidationReviewPanel
        item={{
          ...mockItem,
          model_variant: 'base',
          adapter_resolution: {
            sme: { requested: 'sme-v3', applied: null, reason: 'not_loaded' },
          },
        }}
        onClose={vi.fn()}
      />,
    );

    expect(
      screen.getByText('Adapter sme-v3 requested, base used (not loaded on the server)'),
    ).toBeDefined();
  });

  it('shows no fallback notice when the adapter was applied or base was requested', () => {
    render(
      <ValidationReviewPanel
        item={{
          ...mockItem,
          model_variant: 'adapter',
          adapter_label: 'sme-v3',
          adapter_resolution: {
            sme: { requested: 'sme-v3', applied: 'sme-v3', reason: null },
            gad: { requested: 'base', applied: null, reason: null },
          },
        }}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(/requested, base used/)).toBeNull();
  });
});
