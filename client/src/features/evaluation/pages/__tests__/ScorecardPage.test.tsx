// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScorecardPage } from '../ScorecardPage';

vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ id: 'eval-test-123' }),
}));

vi.mock('../../components/Scorecard', () => ({
  Scorecard: () => <div data-testid="scorecard-fallback">Scorecard Component</div>,
}));
describe('ScorecardPage', () => {
  it('renders the Scorecard component', () => {
    render(<ScorecardPage />);
    expect(screen.getByTestId('scorecard-fallback')).toBeDefined();
  });
});
