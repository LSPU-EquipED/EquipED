// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EvaluationMindMap } from '../EvaluationMindMap';

describe('EvaluationMindMap', () => {
  afterEach(cleanup);

  it('renders truthful source coverage summary without operational claims', () => {
    render(<EvaluationMindMap />);

    expect(screen.getAllByText('Authoritative sources').length).toBeGreaterThan(0);
    expect(screen.getByText('Reference source types')).toBeDefined();
    expect(screen.getByText('Institutional reference materials')).toBeDefined();
    expect(screen.getByText('Review topics')).toBeDefined();
    expect(screen.getByText('Curricular and coverage topics')).toBeDefined();
    expect(screen.getAllByText('Evaluation consumers').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Grounding path' })).toBeDefined();

    // Verify operational claims and backend health phrases are absent
    expect(screen.queryByText(/Indexed and ready/i)).toBeNull();
    expect(screen.queryByText(/Indexed/i)).toBeNull();
    expect(screen.queryByText(/Available for reference lookup/i)).toBeNull();
    expect(screen.queryByText(/Needs attention/i)).toBeNull();
    expect(screen.queryByText(/Evidence available/i)).toBeNull();
    expect(screen.queryByText(/Last update/i)).toBeNull();
    expect(screen.queryByText(/Revision \d+ ·? active/i)).toBeNull();
    expect(screen.queryByText(/Updated from Reference Library/i)).toBeNull();
    expect(screen.queryByText(/Review program coverage/i)).toBeNull();
  });

  it('renders 4 source nodes, 5 consumer nodes, and relationship indicators', () => {
    render(<EvaluationMindMap />);

    // 4 source nodes
    expect(screen.getByRole('button', { name: /Published rubric sets/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Course syllabi/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Degree curricula/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Institutional policies/i })).toBeDefined();

    // 5 consumers
    expect(screen.getByText('SME review')).toBeDefined();
    expect(screen.getByText('Coordinator review')).toBeDefined();
    expect(screen.getByText('GAD review')).toBeDefined();
    expect(screen.getByText('ITSO review')).toBeDefined();
    expect(screen.getByText('Master synthesis')).toBeDefined();

    // Relationship legend
    expect(screen.getByText('Selected relationship')).toBeDefined();
    expect(screen.getByText('Other relationships')).toBeDefined();
    expect(screen.getByText('Grounds evaluation')).toBeDefined();
  });

  it('updates the grounding path and details when a source is selected', () => {
    render(<EvaluationMindMap />);

    const syllabusBtn = screen.getByRole('button', { name: /Course syllabi/i });
    fireEvent.click(syllabusBtn);

    // Detail header updates to Course syllabi
    expect(screen.getByRole('heading', { name: 'Course syllabi' })).toBeDefined();
    expect(syllabusBtn.getAttribute('aria-pressed')).toBe('true');
  });

  it('renders source library, visual grounding path SVG, and detail panel with truthful role copy', () => {
    render(<EvaluationMindMap />);

    expect(screen.getByRole('heading', { name: 'Grounding path' })).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Source details' })).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Published rubric sets' })).toBeDefined();
    expect(screen.getByRole('img', { name: 'Knowledge map connections' })).toBeDefined();
    expect(screen.getAllByText('Reference').length).toBeGreaterThan(0);
    expect(screen.getByText('Illustrative relationship.')).toBeDefined();
    expect(screen.getByText('Reference context')).toBeDefined();
    expect(screen.getByRole('link', { name: /Open reference library/i })).toBeDefined();

    // Verify operational claims are absent in detail panel
    expect(screen.queryByText(/Available/i)).toBeNull();
    expect(screen.queryByText(/Ready/i)).toBeNull();
    expect(screen.queryByText(/Indexed/i)).toBeNull();

    // Select review-topic source (Degree curricula) and assert truthful review copy
    const curriculaBtn = screen.getByRole('button', { name: /Degree curricula/i });
    fireEvent.click(curriculaBtn);
    expect(screen.getByText('Review this source type.')).toBeDefined();
    expect(screen.queryByText(/Available/i)).toBeNull();
    expect(screen.queryByText(/Ready/i)).toBeNull();
    expect(screen.queryByText(/Indexed/i)).toBeNull();
  });

  it('filters sources when filter pill is clicked and selects first matching source', () => {
    render(<EvaluationMindMap />);

    const syllabusFilterBtn = screen.getByRole('button', { name: 'Syllabi' });
    fireEvent.click(syllabusFilterBtn);

    expect(syllabusFilterBtn.getAttribute('aria-pressed')).toBe('true');
    // Syllabi source node visible
    expect(screen.getByRole('button', { name: /Course syllabi/i })).toBeDefined();
    // Rubrics source node hidden when filtered to Syllabi
    expect(screen.queryByRole('button', { name: /Published rubric sets/i })).toBeNull();
    // Detail header updates to Course syllabi
    expect(screen.getByRole('heading', { name: 'Course syllabi' })).toBeDefined();
  });

  it('renders SVG curves linking to visible source relationships', () => {
    render(<EvaluationMindMap />);
    const svg = screen.getByRole('img', { name: 'Knowledge map connections' });
    const paths = svg.querySelectorAll('path');
    expect(paths.length).toBeGreaterThan(0);
    // Ensure all rendered connection paths have valid curve syntax
    paths.forEach((path) => {
      const d = path.getAttribute('d');
      expect(d).toMatch(/^M \d+(\.\d+)? \d+(\.\d+)? C/);
    });
  });
});
