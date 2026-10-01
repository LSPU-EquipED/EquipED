// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { EvaluationStageTracker } from '../EvaluationStageTracker';

afterEach(cleanup);

describe('EvaluationStageTracker', () => {
  it.each([
    ['SUBMITTED', 'Queued'],
    ['PREPROCESSING', 'Preparing the module'],
    ['EVALUATING', 'Specialist review'],
    ['SYNTHESIZING', 'Finalizing results'],
  ])('marks and announces the current %s stage', (status, label) => {
    render(<EvaluationStageTracker status={status} specialistLabel="SME" />);

    const stages = screen.getByRole('list', { name: 'Evaluation stages' });
    expect(stages.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(screen.getByText(label).closest('li')?.getAttribute('aria-current')).toBe('step');
    expect(screen.getByRole('status').textContent).toBe(`SME · ${label}`);
  });

  it.each(['PENDING', 'PROCESSING', 'unknown'])('keeps the existing fallback for %s', (status) => {
    render(<EvaluationStageTracker status={status} specialistLabel="Evaluation" />);

    expect(screen.getByRole('list').querySelector('[aria-current]')).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('Evaluation · In progress');
  });

  it('updates the current step and live announcement as an evaluation advances', () => {
    const { rerender } = render(<EvaluationStageTracker status="PREPROCESSING" specialistLabel="GAD" />);
    rerender(<EvaluationStageTracker status="EVALUATING" specialistLabel="GAD" />);

    expect(screen.getByText('Preparing the module').closest('li')?.hasAttribute('aria-current')).toBe(false);
    expect(screen.getByText('Specialist review').closest('li')?.getAttribute('aria-current')).toBe('step');
    expect(screen.getByRole('status').textContent).toBe('GAD · Specialist review');
  });
});
