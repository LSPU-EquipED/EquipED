// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FineTuningResults } from '../FineTuningResults';
import { modelValidationApi } from '../../api/modelValidation.api';
import archive from '../../../../../../server/modules/admin/data/fine_tuning_results.json';
import type { FineTuningArchive } from '../../archiveTypes';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function chooseExperiment(title: string) {
  fireEvent.click(screen.getByRole('button', { name: 'Experiment' }));
  fireEvent.click(screen.getByRole('option', { name: title }));
}

describe('FineTuningResults', () => {
  it('uses keyboard-operable experiment selection without a duplicate page header', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue(
      archive as FineTuningArchive,
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    const trigger = await screen.findByRole('button', { name: 'Experiment' });
    expect(screen.queryByRole('heading', { name: 'Fine-Tuning Results' })).toBeNull();
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const menu = screen.getByRole('listbox', { name: 'Experiment' });
    fireEvent.keyDown(menu, { key: 'End' });
    fireEvent.keyDown(menu, { key: 'Enter' });
    expect(trigger.textContent).toContain(archive.experiments.at(-1)!.title);
    expect(screen.queryByRole('listbox', { name: 'Experiment' })).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('keeps the chosen SLM and criterion connected to their captured outputs', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue(
      archive as FineTuningArchive,
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    await screen.findByRole('button', { name: 'Experiment' });
    fireEvent.click(screen.getByText('Experiment details'));
    fireEvent.click(screen.getByRole('button', { name: 'Evidence & reasoning' }));
    const run = archive.experiments[0].runs[1];
    const criterion = run.criteria[0];
    fireEvent.click(screen.getByRole('button', { name: 'SLM comparison' }));
    fireEvent.click(screen.getByRole('option', { name: run.title }));
    fireEvent.click(screen.getByRole('button', { name: 'Criterion' }));
    fireEvent.click(screen.getByRole('option', { name: `${criterion.id} — ${criterion.title}` }));
    expect(
      screen.getByRole('heading', { name: `${criterion.id} — ${criterion.title}` }),
    ).toBeDefined();
    for (const [label, output] of [
      ['Base', criterion.base],
      ['Fine-tuned model', criterion.adapter],
    ] as const) {
      const panel = screen.getByRole('region', { name: `${label} archived explanation` });
      expect(within(panel).getByText(output.reasoning!)).toBeDefined();
    }
    chooseExperiment('Rubric Interpretation');
    expect(screen.getByText('Experiment details').closest('details')?.open).toBe(false);
  });

  it('highlights GAD grounding while retaining all held-out scoring outcomes', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue(
      archive as FineTuningArchive,
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    await screen.findByRole('button', { name: 'Experiment' });
    chooseExperiment('Quotation Grounding');
    expect(screen.getByRole('heading', { name: 'Exact quotation grounding' })).toBeDefined();
    expect(screen.getByText('82.5%')).toBeDefined();
    expect(screen.getByText('97.5%')).toBeDefined();
    expect(screen.getByText(/33\/40 → 39\/40/)).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Result summary' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Reasoning quality' })).toBeNull();
    expect(screen.queryByText('Evidence relevance')).toBeNull();
    expect(screen.getByRole('button', { name: 'Experiment' }).textContent).toContain(
      'Quotation Grounding',
    );
    const accuracy = screen.getByRole('figure', { name: 'Mean absolute error comparison' });
    expect(within(accuracy).getByText('0.625')).toBeDefined();
    expect(within(accuracy).getByText('0.650')).toBeDefined();
    expect(within(accuracy).getByText('3')).toBeDefined();
    expect(screen.getByText('Experiment details').closest('details')?.open).toBe(false);
    fireEvent.click(screen.getByText('Experiment details'));
    expect(screen.getByText('Experiment details').closest('details')?.open).toBe(true);
    const comparison = screen.getByRole('figure', { name: 'MAE by SLM' });
    expect(within(comparison).getAllByRole('group')).toHaveLength(8);
    expect(within(comparison).getByText('Base MAE')).toBeDefined();
    expect(within(comparison).getByText('Fine-tuned MAE')).toBeDefined();
    expect(screen.getAllByRole('row')).toHaveLength(9);
    fireEvent.click(screen.getByRole('button', { name: 'Evidence & reasoning' }));
    expect(
      screen.getByRole('region', {
        name: 'Fine-tuned model archived explanation',
      }),
    ).toBeDefined();
    expect(screen.getAllByText(/Quote grounding:/)).toHaveLength(2);
    fireEvent.click(screen.getByText('Experiment details'));
    expect(screen.getByText('Experiment details').closest('details')?.open).toBe(false);
  });
  it('combines every experiment in one selector and hides unmeasured metrics', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue(
      archive as FineTuningArchive,
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    await screen.findByRole('button', { name: 'Experiment' });
    fireEvent.click(screen.getByRole('button', { name: 'Experiment' }));
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(
      archive.experiments.map((experiment) => experiment.title),
    );
    fireEvent.keyDown(screen.getByRole('listbox', { name: 'Experiment' }), { key: 'Escape' });
    for (const name of ['SME', 'GAD', 'Coordinator', 'ITSO']) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
    expect(screen.getByRole('heading', { name: 'Scoring accuracy' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Evidence quality' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Reasoning quality' })).toBeNull();
    expect(screen.queryByText('Not yet formally assessed')).toBeNull();
    expect(screen.queryByText('Quotation grounding not audited.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Training' })).toBeNull();
    chooseExperiment('Rubric Interpretation');
    fireEvent.click(screen.getByText('Experiment details'));
    expect(screen.getByText(/All archived criteria included/)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Training' }));
    expect(screen.getByRole('table', { name: 'Archived training metrics' })).toBeDefined();
    expect(screen.getByRole('figure', { name: 'DPO loss comparison' })).toBeDefined();
    expect(
      screen.getByRole('figure', { name: 'Preference reward margin comparison' }),
    ).toBeDefined();
    chooseExperiment('Synthetic Score Corrections');
    expect(screen.queryByRole('button', { name: 'Training' })).toBeNull();
    expect(screen.getByText('Experiment details').closest('details')?.open).toBe(false);
    fireEvent.click(screen.getByText('Experiment details'));
    expect(screen.getByRole('table', { name: 'Archived results by SLM' })).toBeDefined();
  });
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
      await screen.findByRole('button', { name: 'Experiment' }, { timeout: 5000 }),
    ).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Result summary' })).toBeNull();
    fireEvent.click(screen.getByText('Experiment details'));
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

  it('omits scoring and grounding when no comparable model responses exist', async () => {
    const experiment = structuredClone(archive.experiments.find((e) => e.id === 'gad-v5')!);
    for (const run of experiment.runs) {
      for (const criterion of run.criteria) {
        criterion.base.status = 'fallback';
        criterion.adapter.status = 'fallback';
      }
    }
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue({
      ...archive,
      experiments: [experiment],
    } as FineTuningArchive);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    await screen.findByRole('button', { name: 'Experiment' });
    expect(screen.queryByRole('region', { name: 'Evaluation overview' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Comparisons' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Reasoning quality' })).toBeNull();
  });

  it('exports the selected experiment with its original identity and provenance', async () => {
    vi.spyOn(modelValidationApi, 'getFineTuningArchive').mockResolvedValue(
      archive as FineTuningArchive,
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <FineTuningResults />
      </QueryClientProvider>,
    );
    await screen.findByRole('button', { name: 'Experiment' });
    chooseExperiment('Quotation Grounding');
    const create = vi.fn((_blob: Blob) => 'blob:archive');
    const revoke = vi.fn();
    const OriginalURL = URL;
    vi.stubGlobal(
      'URL',
      class extends OriginalURL {
        static createObjectURL = create;
        static revokeObjectURL = revoke;
      },
    );
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Export results' }));
      const blob = create.mock.calls[0][0];
      const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = reject;
        reader.readAsText(blob);
      });
      expect(JSON.parse(content)).toEqual({
        schema_version: archive.schema_version,
        archived_on: archive.archived_on,
        experiment: archive.experiments.find((experiment) => experiment.id === 'gad-v5'),
      });
      await waitFor(() => expect(revoke).toHaveBeenCalledWith('blob:archive'), { timeout: 2000 });
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
