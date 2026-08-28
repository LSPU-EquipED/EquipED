// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { RubricTableEditor } from '../RubricTableEditor';
import type { RubricSetListResponse } from '../../types';

const mockData: RubricSetListResponse = {
  rubric_sets: [
    {
      rubric_set_id: 'set-sme',
      agent_id: 'sme',
      name: 'SME Rubric v1',
      version_number: 1,
      status: 'active',
      domains: [
        {
          rubric_domain_id: 'dom-op',
          code: 'OP',
          title: 'Organization & Presentation',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-op1',
              criterion_code: 'OP-01',
              title: 'Topic Coherence',
              description: 'Topics are coherent from Unit to Chapter.',
              display_order: 1,
            },
          ],
        },
      ],
    },
  ],
};

const updateCriterionMutate = vi.fn();
const updateDomainMutate = vi.fn();

vi.mock('../../hooks/useRubrics', () => ({
  useRubricSets: () => ({ data: mockData, isLoading: false, isError: false, error: null }),
  useUpdateCriterion: () => ({ mutate: updateCriterionMutate, isPending: false }),
  useUpdateDomain: () => ({ mutate: updateDomainMutate, isPending: false }),
  getRubricOperationError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

describe('RubricTableEditor', () => {
  beforeEach(() => {
    updateCriterionMutate.mockClear();
    updateDomainMutate.mockClear();
  });
  afterEach(cleanup);

  it('renders the real criterion code and text from the server, not hardcoded data', () => {
    render(<RubricTableEditor />);

    expect(screen.getByDisplayValue('OP-01')).toBeDefined();
    expect(screen.getByDisplayValue('Topic Coherence')).toBeDefined();
    expect(screen.getByDisplayValue('Topics are coherent from Unit to Chapter.')).toBeDefined();
    // The old fake seed data must be gone.
    expect(screen.queryByDisplayValue('Content accuracy')).toBeNull();
  });

  it('saves an edited title via the update-criterion mutation', () => {
    render(<RubricTableEditor />);

    fireEvent.click(screen.getByRole('button', { name: /edit .*OP-01/i }));
    const titleInput = screen.getByDisplayValue('Topic Coherence');
    fireEvent.change(titleInput, { target: { value: 'Topic Flow' } });
    fireEvent.click(screen.getByRole('button', { name: /finish editing .*OP-01/i }));

    expect(updateCriterionMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        criterionId: 'crit-op1',
        body: {
          title: 'Topic Flow',
          description: 'Topics are coherent from Unit to Chapter.',
        },
      }),
    );
  });

  it('keeps the criterion code read-only and structural buttons disabled', () => {
    render(<RubricTableEditor />);

    expect((screen.getByDisplayValue('OP-01') as HTMLInputElement).readOnly).toBe(true);
    const addRow = screen.getByRole('button', { name: /add row/i }) as HTMLButtonElement;
    expect(addRow.disabled).toBe(true);
    const addTable = screen.getByRole('button', { name: /add table/i }) as HTMLButtonElement;
    expect(addTable.disabled).toBe(true);
  });
});
