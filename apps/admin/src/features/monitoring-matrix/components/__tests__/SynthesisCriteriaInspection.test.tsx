// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React, { useState } from 'react';
import { SynthesisCriteriaInspection } from '../SynthesisCriteriaInspection';
import type { MatrixCriterionScoreItem } from '../../types';

const mockCriteriaA: MatrixCriterionScoreItem[] = [
  {
    criterion_id: 'CRIT-1',
    criterion_text: 'Pedagogical Structure',
    description: 'Structure follows syllabus sequence',
    score: 4,
    justification: 'Clear sequence from fundamentals to advanced.',
    evidence: 'Module 1 outlines sequencing.',
  },
  {
    criterion_id: 'CRIT-2',
    criterion_text: 'Learning Outcomes Alignment',
    description: 'Activities map to learning outcomes',
    score: 3,
    justification: 'Most activities match CLO 1 and 2.',
    evidence: 'Activity rubric table.',
  },
];

const mockCriteriaB: MatrixCriterionScoreItem[] = [
  {
    criterion_id: 'CRIT-1', // Same key name to test overlapping keys across tabs
    criterion_text: 'Inclusive Language',
    description: 'Avoids gender-biased terminology',
    score: 4,
    justification: 'Inclusive language guidelines met.',
    evidence: 'Glossary section.',
  },
  {
    criterion_id: 'CRIT-3',
    criterion_text: 'Universal Design for Learning',
    description: 'Provides multiple means of representation',
    score: 3,
    justification: 'Captioned media and transcripts included.',
  },
];

describe('SynthesisCriteriaInspection', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders criteria list with titles and scores', () => {
    render(<SynthesisCriteriaInspection criteria={mockCriteriaA} />);

    expect(screen.getByText('Rubric criteria assessment')).toBeDefined();
    expect(screen.getByText('(2)')).toBeDefined();
    expect(screen.getByText('Pedagogical Structure')).toBeDefined();
    expect(screen.getByText('Learning Outcomes Alignment')).toBeDefined();
    expect(screen.getByText('4 / 4')).toBeDefined();
    expect(screen.getByText('3 / 4')).toBeDefined();
  });

  it('renders fallback when criteria is empty', () => {
    render(<SynthesisCriteriaInspection criteria={[]} />);

    expect(screen.getByText('No specific criteria items recorded for this pillar yet.')).toBeDefined();
  });

  it('toggles individual criterion expansion via mouse click and keyboard (Enter and Space)', () => {
    render(<SynthesisCriteriaInspection criteria={mockCriteriaA} />);

    const crit1Header = screen.getByRole('button', { name: /CRIT-1 Pedagogical Structure/i });
    expect(crit1Header.getAttribute('aria-expanded')).toBe('false');

    // Toggle open via click
    fireEvent.click(crit1Header);
    expect(crit1Header.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('Clear sequence from fundamentals to advanced.')).toBeDefined();

    // Toggle closed via Enter key
    fireEvent.keyDown(crit1Header, { key: 'Enter' });
    expect(crit1Header.getAttribute('aria-expanded')).toBe('false');

    // Toggle open via Space key
    fireEvent.keyDown(crit1Header, { key: ' ' });
    expect(crit1Header.getAttribute('aria-expanded')).toBe('true');
  });

  it('handles expand-all and collapse-all toggling', () => {
    render(<SynthesisCriteriaInspection criteria={mockCriteriaA} />);

    const toggleAllBtn = screen.getByRole('button', { name: /expand all/i });
    expect(toggleAllBtn).toBeDefined();

    const crit1Header = screen.getByRole('button', { name: /CRIT-1 Pedagogical Structure/i });
    const crit2Header = screen.getByRole('button', { name: /CRIT-2 Learning Outcomes Alignment/i });
    expect(crit1Header.getAttribute('aria-expanded')).toBe('false');
    expect(crit2Header.getAttribute('aria-expanded')).toBe('false');

    // Expand all
    fireEvent.click(toggleAllBtn);
    expect(screen.getByRole('button', { name: /collapse all/i })).toBeDefined();
    expect(crit1Header.getAttribute('aria-expanded')).toBe('true');
    expect(crit2Header.getAttribute('aria-expanded')).toBe('true');

    // Collapse all
    const collapseAllBtn = screen.getByRole('button', { name: /collapse all/i });
    fireEvent.click(collapseAllBtn);
    expect(screen.getByRole('button', { name: /expand all/i })).toBeDefined();
    expect(crit1Header.getAttribute('aria-expanded')).toBe('false');
    expect(crit2Header.getAttribute('aria-expanded')).toBe('false');
  });

  it('keeps expansion independent when switching pillars with overlapping criterion IDs', () => {
    function ParentHarness() {
      const [pillar, setPillar] = useState<'A' | 'B'>('A');
      return (
        <div>
          <button type="button" onClick={() => setPillar('A')}>
            Tab A
          </button>
          <button type="button" onClick={() => setPillar('B')}>
            Tab B
          </button>
          <SynthesisCriteriaInspection key={pillar} criteria={pillar === 'A' ? mockCriteriaA : mockCriteriaB} />
        </div>
      );
    }

    render(<ParentHarness />);

    // In Tab A, expand CRIT-1
    const crit1HeaderA = screen.getByRole('button', { name: /CRIT-1 Pedagogical Structure/i });
    fireEvent.click(crit1HeaderA);
    expect(crit1HeaderA.getAttribute('aria-expanded')).toBe('true');

    // Switching pillars remounts the criteria list, so expansion does not leak.
    fireEvent.click(screen.getByRole('button', { name: 'Tab B' }));

    // In Tab B, the same ID starts collapsed.
    const crit1HeaderB = screen.getByRole('button', { name: /CRIT-1 Inclusive Language/i });
    expect(crit1HeaderB.getAttribute('aria-expanded')).toBe('false');

    // CRIT-3 was not expanded
    const crit3HeaderB = screen.getByRole('button', { name: /CRIT-3 Universal Design for Learning/i });
    expect(crit3HeaderB.getAttribute('aria-expanded')).toBe('false');
  });
});
