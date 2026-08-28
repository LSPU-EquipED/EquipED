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
              scoring_rule: '0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.',
              display_order: 1,
            },
          ],
        },
      ],
    },
    {
      rubric_set_id: 'set-gad',
      agent_id: 'gad',
      name: 'GAD Rubric v1',
      version_number: 1,
      status: 'active',
      domains: [
        {
          rubric_domain_id: 'dom-gad',
          code: 'GAD',
          title: 'Inclusivity',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-gad1',
              criterion_code: 'GAD-01',
              title: 'Free from Stereotypes',
              description: 'The material is free from gender stereotypes.',
              scoring_rule: null,
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

  it('renders Criterion ID, Entry and Scoring rule columns, no Field column', () => {
    render(<RubricTableEditor />);

    expect(screen.queryByRole('columnheader', { name: /^field$/i })).toBeNull();
    expect(screen.getAllByRole('columnheader', { name: /scoring rule/i }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByDisplayValue('OP-01')).toBeDefined();
    expect(screen.getByDisplayValue('Topics are coherent from Unit to Chapter.')).toBeDefined();
    expect(screen.getByDisplayValue('0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.')).toBeDefined();
  });

  it('saves description + scoring rule via the update-criterion mutation', () => {
    render(<RubricTableEditor />);

    fireEvent.click(screen.getByRole('button', { name: /edit .*OP-01/i }));
    fireEvent.change(screen.getByDisplayValue('0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.'), {
      target: { value: 'EDITED RULE' },
    });
    fireEvent.click(screen.getByRole('button', { name: /finish editing .*OP-01/i }));

    expect(updateCriterionMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        criterionId: 'crit-op1',
        body: {
          description: 'Topics are coherent from Unit to Chapter.',
          scoring_rule: 'EDITED RULE',
        },
      }),
    );
  });

  it('shows a "not used yet" note for non-SME agents', () => {
    render(<RubricTableEditor />);
    expect(screen.getByText(/not used by this agent's scoring yet/i)).toBeDefined();
  });

  it('keeps criterion code read-only and structural buttons disabled', () => {
    render(<RubricTableEditor />);

    expect((screen.getByDisplayValue('OP-01') as HTMLInputElement).readOnly).toBe(true);
    expect(
      (screen.getAllByRole('button', { name: /add row/i })[0] as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getAllByRole('button', { name: /add table/i })[0] as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
