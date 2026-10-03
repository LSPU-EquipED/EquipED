// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TrainingSummaryPanel } from '../TrainingSummaryPanel';

afterEach(cleanup);

it('shows margin, accuracy, loss, steps and the held-out numbers', () => {
  render(
    <TrainingSummaryPanel
      summary={{
        version: 1,
        steps: 12,
        epochs: 3,
        first: { step: 1, margin: 0, loss: 0.69, accuracy: 0.5 },
        last: { step: 12, margin: 1.4, loss: 0.21, accuracy: 1 },
        heldout: { pair_count: 7, margin: 0.9, accuracy: 0.86, loss: 0.4 },
      }}
    />,
  );
  expect(screen.getByText('Training summary')).toBeDefined();
  expect(screen.getByText('0.00 → 1.40')).toBeDefined();
  expect(screen.getByText('100%')).toBeDefined();
  expect(screen.getByText('0.210')).toBeDefined();
  expect(screen.getByText('12 (3 epochs)')).toBeDefined();
  expect(screen.getByText('0.90')).toBeDefined();
  expect(screen.getByText('86%')).toBeDefined();
  expect(screen.getByText(/measured on the training pairs/i)).toBeDefined();
});

it('says "Not recorded" when there is no summary', () => {
  render(<TrainingSummaryPanel summary={null} />);
  expect(screen.getByText('Not recorded')).toBeDefined();
  expect(screen.queryByText(/measured on the training pairs/i)).toBeNull();
});

it('renders only what exists for a partial summary and never prints NaN', () => {
  const { container } = render(
    <TrainingSummaryPanel summary={{ version: 1, last: { margin: 1.25 } }} />,
  );
  expect(screen.getByText('1.25')).toBeDefined();
  expect(container.textContent).not.toMatch(/NaN|undefined|null/);
  expect(screen.queryByText('Preference accuracy')).toBeNull();
});

it('treats an empty summary object as not recorded', () => {
  render(<TrainingSummaryPanel summary={{ version: 1 }} />);
  expect(screen.getByText('Not recorded')).toBeDefined();
});
