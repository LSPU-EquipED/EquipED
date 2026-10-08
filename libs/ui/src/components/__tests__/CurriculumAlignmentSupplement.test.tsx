// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CurriculumAlignmentSupplement } from '../CurriculumAlignmentSupplement';

afterEach(cleanup);

it('keeps the advisory score and every matched/unmatched objective separate', () => {
  render(<CurriculumAlignmentSupplement advisory={{
    contract: 'coordinator_alignment.v1', criterion_id: 'C-01',
    criterion_title: 'Curriculum Alignment', advisory_only: true,
    score: 3, justification: 'One of two objectives supported.',
    objective_matches: [
      { objective_id: 'OBJ-0001', objective_text: 'Add integers.', matched: true, excerpt: 'Curriculum competency: integer addition.', rejected: false },
      { objective_id: 'OBJ-0002', objective_text: 'Explain addition.', matched: false, excerpt: '', rejected: true },
    ],
  }} />);
  expect(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).toBeTruthy();
  expect(screen.getByText('3 / 4')).toBeTruthy();
  expect(screen.getByText(/Excluded from the official subtotal, matrix composite/)).toBeTruthy();
  expect(screen.getByText('Objective evidence (2)')).toBeTruthy();
  expect(screen.getByText('Add integers.')).toBeTruthy();
  expect(screen.getByText('Explain addition.')).toBeTruthy();
  expect(screen.getByText('Curriculum competency: integer addition.')).toBeTruthy();
  expect(screen.getByText(/Not matched to curriculum/)).toBeTruthy();
  expect(screen.getByText(/Unsupported claim rejected/)).toBeTruthy();
});
