// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EvaluationMindMap } from '../EvaluationMindMap';

describe('EvaluationMindMap', () => {
  afterEach(cleanup);

  it('keeps the map focused without a separate metadata strip', () => {
    render(<EvaluationMindMap />);

    expect(
      screen.getByRole('heading', { name: 'Grounding path' }),
    ).toBeDefined();
    expect(screen.queryByText('Reference source types')).toBeNull();
    expect(screen.queryByText('Review topics')).toBeNull();
    expect(screen.queryByText(/Click a source to highlight/i)).toBeNull();

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
    expect(
      screen.getByRole('button', { name: /Published rubric sets/i }),
    ).toBeDefined();
    expect(
      screen.getByRole('button', { name: /Course syllabi/i }),
    ).toBeDefined();
    expect(
      screen.getByRole('button', { name: /Degree curricula/i }),
    ).toBeDefined();
    expect(
      screen.getByRole('button', { name: /Institutional policies/i }),
    ).toBeDefined();

    // 5 consumers
    expect(screen.getByText('SME review')).toBeDefined();
    expect(screen.getByText('Coordinator review')).toBeDefined();
    expect(screen.getByText('GAD review')).toBeDefined();
    expect(screen.getByText('ITSO review')).toBeDefined();
    expect(screen.getByText('Master synthesis')).toBeDefined();

    // Relationship legend
    expect(screen.getByText('Selected relationship')).toBeDefined();
    expect(screen.getByText('Other relationships')).toBeDefined();
    expect(
      screen.getByRole('img', { name: 'Knowledge map connections' }),
    ).toBeDefined();
  });

  it('updates the connected count and highlighted paths when a source is selected', () => {
    render(<EvaluationMindMap />);

    const syllabusBtn = screen.getByRole('button', { name: /Course syllabi/i });
    fireEvent.click(syllabusBtn);

    expect(screen.getByText('Course syllabi')).toBeDefined();
    expect(syllabusBtn.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('2 connected paths')).toBeDefined();
    const svg = screen.getByRole('img', { name: 'Knowledge map connections' });
    expect(svg.querySelectorAll('path:not([stroke-dasharray])')).toHaveLength(2);
    expect(svg.querySelectorAll('circle')).toHaveLength(4);

    fireEvent.click(screen.getByRole('button', { name: /Institutional policies/i }));
    expect(screen.getByText('1 connected path')).toBeDefined();
    expect(svg.querySelectorAll('path:not([stroke-dasharray])')).toHaveLength(1);
    expect(svg.querySelectorAll('circle')).toHaveLength(2);
  });

  it('renders the visual grounding path without a secondary metadata panel', () => {
    render(<EvaluationMindMap />);

    expect(
      screen.getByRole('heading', { name: 'Grounding path' }),
    ).toBeDefined();
    expect(screen.getAllByText('Published rubric sets').length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByRole('img', { name: 'Knowledge map connections' }),
    ).toBeDefined();
    expect(screen.getAllByText('Reference').length).toBeGreaterThan(0);
    expect(screen.queryByText('Source details')).toBeNull();
    expect(
      screen.queryByRole('link', { name: /Open reference library/i }),
    ).toBeNull();

    // Select review-topic source and ensure the map selection updates.
    const curriculaBtn = screen.getByRole('button', {
      name: /Degree curricula/i,
    });
    fireEvent.click(curriculaBtn);
    expect(curriculaBtn.getAttribute('aria-pressed')).toBe('true');
  });

  it('filters sources when filter pill is clicked and selects first matching source', () => {
    render(<EvaluationMindMap />);

    const syllabusFilterBtn = screen.getByRole('button', { name: 'Syllabi' });
    fireEvent.click(syllabusFilterBtn);

    expect(syllabusFilterBtn.getAttribute('aria-pressed')).toBe('true');
    // Syllabi source node visible
    expect(
      screen.getByRole('button', { name: /Course syllabi/i }),
    ).toBeDefined();
    // Rubrics source node hidden when filtered to Syllabi
    expect(
      screen.queryByRole('button', { name: /Published rubric sets/i }),
    ).toBeNull();
    expect(screen.getByText('Course syllabi')).toBeDefined();
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
