// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FineTuningResults } from '../FineTuningResults';
import { modelValidationApi } from '../../api/modelValidation.api';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('FineTuningResults', () => {
  it('keeps the archive readable when the live validation database is empty', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue({
      schema_version: 1,
      archived_on: '2026-10-16',
      experiments: [
        {
          id: 'v7',
          title: 'Synthetic Score Corrections',
          adapter_label: 'sme-v7',
          scope: 'All 10 SME criteria',
          reference_kind: 'Synthetic targets',
          pair_count: 32,
          dataset_note: '25 pairs used for training.',
          summary: 'Small observed gains.',
          limitations: ['One run per condition.'],
          primary_criteria: null,
          training: null,
          runs: [
            {
              title: 'Example SLM',
              base_validation_id: 'base-id',
              adapter_validation_id: 'adapter-id',
              base_evaluation_id: 'base-eval',
              adapter_evaluation_id: 'adapter-eval',
              prompt_hashes: [],
              criteria: [
                {
                  id: 'OP-05',
                  title: 'Enhancement Activities',
                  expected: 4,
                  base: {
                    score: 2,
                    status: 'ok',
                    evidence: ['Exact source passage'],
                    reasoning: 'Base reasoning',
                    stored_justification: null,
                  },
                  adapter: {
                    score: 3,
                    status: 'repaired',
                    evidence: ['Exact source passage'],
                    reasoning: null,
                    stored_justification: 'Stored legacy explanation',
                  },
                  audit_note: 'Audit observation; not an expert label.',
                },
              ],
            },
          ],
        },
      ],
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <FineTuningResults />
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole('combobox', { name: 'Experiment' }, { timeout: 5000 }),
    ).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Result summary' })).toBeDefined();
    expect(screen.getByRole('columnheader', { name: 'Fine-tuned MAE' })).toBeDefined();
    expect(screen.queryByText('One run per condition.')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Method' }));
    expect(screen.getByText('One run per condition.')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Evidence & reasoning' }));
    expect(screen.getByText('Base reasoning')).toBeDefined();
    expect(screen.getByText('Reasoning not stored.')).toBeDefined();
    expect(screen.getByText('Stored legacy explanation')).toBeDefined();
    expect(screen.getByText('Repaired model response')).toBeDefined();
  });
});
