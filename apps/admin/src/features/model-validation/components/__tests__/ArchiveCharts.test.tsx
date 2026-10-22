// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { ArchivedComparison, ArchivedExperiment } from '../../archiveTypes';
import { ArchiveComparisonBars } from '../ArchiveComparisonBars';
import { ArchiveSlmComparisonChart } from '../ArchiveSlmComparisonChart';

afterEach(cleanup);

describe('archive charts', () => {
  it('places negative and positive training margins on the same zero baseline', () => {
    render(
      <ArchiveComparisonBars
        label="Reward margin"
        rows={[
          { label: 'First', value: -2, display: '-2.000000' },
          { label: 'Last', value: 2, display: '2.000000' },
        ]}
      />,
    );
    const figure = screen.getByRole('figure', { name: 'Reward margin' });
    expect(screen.getByText('-2.000000')).toBeDefined();
    expect(screen.getByText('2.000000')).toBeDefined();
    const tracks = figure.querySelectorAll('dl [aria-hidden="true"]');
    const firstBar = tracks[0].lastElementChild as HTMLElement;
    const lastBar = tracks[1].lastElementChild as HTMLElement;
    expect(firstBar.style.left).toBe('0%');
    expect(firstBar.style.width).toBe('50%');
    expect(lastBar.style.left).toBe('50%');
    expect(lastBar.style.width).toBe('50%');
  });

  it('renders zero measurements without inventing a bar or an invalid scale', () => {
    render(
      <ArchiveComparisonBars
        label="Zero loss"
        rows={[
          { label: 'First', value: 0, display: '0.000000' },
          { label: 'Last', value: 0, display: '0.000000' },
        ]}
      />,
    );
    const figure = screen.getByRole('figure', { name: 'Zero loss' });
    expect(screen.getAllByText('0.000000')).toHaveLength(2);
    for (const track of figure.querySelectorAll('dl [aria-hidden="true"]')) {
      expect((track.lastElementChild as HTMLElement).style.width).toBe('0%');
    }
    expect(figure.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it('respects primary criteria, omits fallback pairs, and distinguishes zero from missing data', () => {
    const run = (
      title: string,
      base: number,
      tuned: number,
      fallback = false,
    ): ArchivedComparison => ({
      title,
      base_validation_id: `base-${title}`,
      adapter_validation_id: `tuned-${title}`,
      base_evaluation_id: `base-eval-${title}`,
      adapter_evaluation_id: `tuned-eval-${title}`,
      prompt_hashes: [],
      criteria: [
        {
          id: 'OP-05',
          title: 'Primary',
          expected: 4,
          audit_note: null,
          base: {
            score: base,
            status: fallback ? 'fallback' : 'ok',
            evidence: null,
            reasoning: null,
            stored_justification: null,
          },
          adapter: {
            score: tuned,
            status: 'ok',
            evidence: null,
            reasoning: null,
            stored_justification: null,
          },
        },
        {
          id: 'OTHER',
          title: 'Control',
          expected: 4,
          audit_note: null,
          base: {
            score: 4,
            status: 'ok',
            evidence: null,
            reasoning: null,
            stored_justification: null,
          },
          adapter: {
            score: 1,
            status: 'ok',
            evidence: null,
            reasoning: null,
            stored_justification: null,
          },
        },
      ],
    });
    const experiment: ArchivedExperiment = {
      id: 'test',
      title: 'Primary criterion',
      adapter_label: 'original-model',
      scope: 'OP-05 only',
      reference_kind: 'Synthetic',
      pair_count: null,
      dataset_note: '',
      summary: '',
      limitations: [],
      primary_criteria: ['OP-05'],
      training: null,
      runs: [
        run('Better', 1, 4),
        run('Worse', 4, 3),
        run('Same', 2, 2),
        run('Excluded', 1, 4, true),
      ],
    };
    render(<ArchiveSlmComparisonChart experiment={experiment} />);
    const better = screen.getByRole('group', { name: 'Better' });
    expect(within(better).getByText('Base MAE:').parentElement?.textContent).toBe(
      'Base MAE: 3.000',
    );
    expect(within(better).getByText('Fine-tuned MAE:').parentElement?.textContent).toBe(
      'Fine-tuned MAE: 0.000',
    );
    const bars = better.querySelectorAll('span.h-5');
    expect((bars[0] as HTMLElement).style.width).toBe('100%');
    expect((bars[1] as HTMLElement).style.width).toBe('0%');
    const same = screen.getByRole('group', { name: 'Same' });
    const sameBars = same.querySelectorAll('span.h-5');
    expect((sameBars[0] as HTMLElement).style.width).toBe('100%');
    expect((sameBars[1] as HTMLElement).style.width).toBe('100%');
    expect(within(same).getByText('Base MAE:').parentElement?.textContent).toBe('Base MAE: 2.000');
    expect(within(same).getByText('Fine-tuned MAE:').parentElement?.textContent).toBe(
      'Fine-tuned MAE: 2.000',
    );
    const worse = screen.getByRole('group', { name: 'Worse' });
    expect(within(worse).getByText('Base MAE:').parentElement?.textContent).toBe('Base MAE: 0.000');
    expect(within(worse).getByText('Fine-tuned MAE:').parentElement?.textContent).toBe(
      'Fine-tuned MAE: 1.000',
    );
    expect((worse.querySelectorAll('span.h-5')[1] as HTMLElement).style.width).toBe('50%');
    expect(screen.getByText(/Bars above 2 stop at the axis limit/)).toBeDefined();
    expect(screen.queryByText('Excluded')).toBeNull();
  });
});
