// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import type { HistoryEvaluationItem } from '../../types';
import { formatDate } from '../../utils/historyFormatters';
import { HistoryRows } from '../HistoryRows';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    params,
    children,
    ...props
  }: {
    to: string;
    params?: Record<string, string>;
    children?: ReactNode;
  } & ComponentPropsWithoutRef<'a'>) => {
    const href = Object.entries(params ?? {}).reduce(
      (url, [key, value]) => url.replace(`$${key}`, value),
      to,
    );
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const completed: HistoryEvaluationItem = {
  evaluation_id: 'run-completed',
  document_id: 'module-1',
  document_title: 'Operating Systems SLM',
  target_agent: 'sme',
  status: 'COMPLETED',
  submitted_at: '2026-10-01T10:00:00Z',
  completed_at: '2026-10-01T10:02:00Z',
  duration_seconds: 120,
  syllabus_id: 'syllabus-1',
  curriculum_id: 'curriculum-1',
  error_message: null,
  confirmed_program: 'BSCS',
};

function renderRows(items = [completed]) {
  return render(
    <HistoryRows
      items={items}
      isLoading={false}
      isFetching={false}
      isError={false}
      hasData
      hasActiveFilters={false}
      onResetFilters={vi.fn()}
    />,
  );
}

describe('simplified history rows', () => {
  it('prioritizes four columns and leaves technical details behind the disclosure', () => {
    const { container } = renderRows();
    expect(
      screen.getAllByRole('columnheader').map((header) => header.textContent),
    ).toEqual(['Module', 'Status', 'Submitted', 'Action']);
    expect(screen.getByText('Completed')).toBeDefined();
    expect(screen.getByText(formatDate(completed.submitted_at))).toBeDefined();
    expect(screen.queryByText(completed.evaluation_id)).toBeNull();
    expect(screen.queryByText('2m 0s')).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Copy full evaluation ID' }),
    ).toBeNull();
    // The only icon left in the main row operates its details disclosure.
    expect(
      container.querySelector('tbody tr')?.querySelectorAll('svg'),
    ).toHaveLength(1);
    expect(
      screen
        .getByRole('link', {
          name: `View evaluation results for ${completed.document_title}`,
        })
        .getAttribute('href'),
    ).toBe('/evaluations/run-completed');
  });

  it('reveals complete run metadata, preserves navigation and copies the full ID', () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
    renderRows();
    const expand = screen.getByRole('button', {
      name: `Expand details for ${completed.document_title}`,
    });
    fireEvent.click(expand);
    expect(expand.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('Run details')).toBeDefined();
    for (const text of [
      completed.evaluation_id,
      completed.document_id,
      'syllabus-1',
      'curriculum-1',
      '2m 0s',
      formatDate(completed.completed_at!),
    ]) {
      expect(screen.getByText(text)).toBeDefined();
    }
    expect(
      screen.getByRole('link', { name: 'Module Library' }).getAttribute('href'),
    ).toBe('/documents');
    expect(
      screen.getByRole('link', { name: 'SME workspace' }).getAttribute('href'),
    ).toBe('/specialists/sme/module-1');
    fireEvent.click(
      screen.getByRole('button', { name: 'Copy full evaluation ID' }),
    );
    expect(writeText).toHaveBeenCalledWith('run-completed');
    expect(screen.getByText('Copied')).toBeDefined();
    fireEvent.click(expand);
    expect(screen.queryByText('Run details')).toBeNull();
  });

  it('keeps failed and active runs truthful while linking to the recorded run', () => {
    const failed = {
      ...completed,
      evaluation_id: 'run-failed',
      status: 'FAILED',
      completed_at: null,
      duration_seconds: null,
      error_message: 'Reference unavailable.',
    };
    const active = {
      ...completed,
      evaluation_id: 'run-active',
      status: 'EVALUATING',
      completed_at: null,
      duration_seconds: null,
    };
    renderRows([failed, active]);
    expect(screen.getByText('Failed')).toBeDefined();
    expect(screen.getByText('Evaluating')).toBeDefined();
    expect(
      screen
        .getByRole('link', {
          name: `View details for ${completed.document_title}`,
        })
        .getAttribute('href'),
    ).toBe('/evaluations/run-failed');
    expect(
      screen
        .getByRole('link', {
          name: `View progress for ${completed.document_title}`,
        })
        .getAttribute('href'),
    ).toBe('/evaluations/run-active');
    fireEvent.click(
      screen.getAllByRole('button', {
        name: `Expand details for ${completed.document_title}`,
      })[0],
    );
    expect(screen.getByText('Reference unavailable.')).toBeDefined();
    expect(screen.queryByText('In progress…')).toBeNull();
    const completedField = screen.getByText('Completed').parentElement!;
    expect(within(completedField).getByText('—')).toBeDefined();
  });

  it('distinguishes repeat submissions by timestamp and keeps each result link exact', () => {
    const repeated = {
      ...completed,
      evaluation_id: 'run-repeated',
      submitted_at: '2026-10-01T10:15:00Z',
    };
    renderRows([completed, repeated]);
    expect(screen.getByText(formatDate(completed.submitted_at))).toBeDefined();
    expect(screen.getByText(formatDate(repeated.submitted_at))).toBeDefined();
    expect(
      screen.getAllByRole('link').map((link) => link.getAttribute('href')),
    ).toEqual(['/evaluations/run-completed', '/evaluations/run-repeated']);
  });
});
