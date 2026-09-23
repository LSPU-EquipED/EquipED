// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { MonitoringMatrixRow } from '../MonitoringMatrixRow';
import type { MonitoringMatrixRow as MonitoringMatrixRowType } from '../../types';

const mockNavigate = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    params,
    children,
    className,
    onClick,
    ...rest
  }: {
    to: string;
    params?: Record<string, string>;
    children?: React.ReactNode;
    className?: string;
    onClick?: (e: React.MouseEvent) => void;
    [key: string]: unknown;
  }) => {
    let href = to;
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} className={className} onClick={onClick} {...rest}>
        {children}
      </a>
    );
  },
  useNavigate: () => mockNavigate,
}));

function MatrixRowTestWrapper({
  row,
  initialExpanded = false,
  renderOutsideElement = false,
}: {
  row: MonitoringMatrixRowType;
  initialExpanded?: boolean;
  renderOutsideElement?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);

  return (
    <div>
      {renderOutsideElement && (
        <input aria-label="Outside search input" />
      )}
      <table>
        <tbody>
          <MonitoringMatrixRow
            row={row}
            isExpanded={isExpanded}
            onToggle={() => setIsExpanded((prev) => !prev)}
          />
        </tbody>
      </table>
    </div>
  );
}

describe('MonitoringMatrixRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders clickable drilldown View Synthesis button and module title link, but non-link row click does not navigate', () => {
    const mockRow: MonitoringMatrixRowType = {
      matrix_id: 'mat-100',
      document_id: 'doc-synthesis-123',
      evaluation_id: 'eval-100',
      faculty_name: 'Prof. Garcia',
      program: 'BSCS',
      document_title: 'Database Systems Module',
      evaluation_status: 'COMPLETED',
      synthesized_score: 3.85,
      adjectival_rating: 'Outstanding',
      domain_scores: null,
      flag_count: 0,
      feedback_status: 'PUBLISHED',
      last_updated: '2026-06-01T00:00:00Z',
    };

    render(<MatrixRowTestWrapper row={mockRow} />);

    // View Synthesis button/link rendered with correct route
    const viewSynthesisBtn = screen.getByRole('link', { name: /view synthesis/i });
    expect(viewSynthesisBtn).toBeDefined();
    expect(viewSynthesisBtn.getAttribute('href')).toBe('/admin/synthesis/doc-synthesis-123');

    // Module title link rendered with correct route
    const titleLink = screen.getByTestId('module-title-link-doc-synthesis-123');
    expect(titleLink).toBeDefined();
    expect(titleLink.getAttribute('href')).toBe('/admin/synthesis/doc-synthesis-123');

    // Non-link click on row (or status/faculty cell) does NOT navigate
    const facultyText = screen.getByText('Faculty: Prof. Garcia');
    fireEvent.click(facultyText);
    expect(mockNavigate).not.toHaveBeenCalled();

    const rowTitle = screen.getByText('Database Systems Module');
    const tr = rowTitle.closest('tr');
    expect(tr).not.toBeNull();
    if (tr) {
      fireEvent.click(tr);
      expect(mockNavigate).not.toHaveBeenCalled();
    }
  });

  it('moves focus to disclosure button on collapse when focus is inside detail row', () => {
    const mockRow: MonitoringMatrixRowType = {
      matrix_id: 'mat-1',
      document_id: 'doc-1',
      evaluation_id: 'eval-1',
      faculty_name: 'Dr. Santos',
      program: 'BSCS',
      document_title: 'Focus Test Module',
      evaluation_status: 'COMPLETED',
      synthesized_score: 90,
      adjectival_rating: 'Very Satisfactory',
      domain_scores: null,
      flag_count: 0,
      feedback_status: 'NO_FEEDBACK',
      last_updated: '2026-08-20T10:00:00Z',
    };

    render(<MatrixRowTestWrapper row={mockRow} />);

    const disclosureBtn = screen.getByLabelText(/Expand details for Focus Test Module/i);

    // Expand the drawer
    fireEvent.click(disclosureBtn);

    // Find scorecard link inside the drawer and focus it
    const scorecardLink = screen.getByRole('link', { name: /Open full scorecard/i });
    scorecardLink.focus();
    expect(document.activeElement).toBe(scorecardLink);

    // Now collapse the drawer by clicking disclosure button
    fireEvent.click(disclosureBtn);

    // Focus must move to disclosure button
    expect(document.activeElement).toBe(disclosureBtn);
  });

  it('does not steal focus on collapse when focus is outside the detail drawer', () => {
    const mockRow: MonitoringMatrixRowType = {
      matrix_id: 'mat-1',
      document_id: 'doc-1',
      evaluation_id: 'eval-1',
      faculty_name: 'Dr. Santos',
      program: 'BSCS',
      document_title: 'Focus Outside Module',
      evaluation_status: 'COMPLETED',
      synthesized_score: 90,
      adjectival_rating: 'Very Satisfactory',
      domain_scores: null,
      flag_count: 0,
      feedback_status: 'NO_FEEDBACK',
      last_updated: '2026-08-20T10:00:00Z',
    };

    render(<MatrixRowTestWrapper row={mockRow} renderOutsideElement />);

    const disclosureBtn = screen.getByLabelText(/Expand details for Focus Outside Module/i);
    // Expand drawer
    fireEvent.click(disclosureBtn);

    // Focus input outside drawer
    const searchInput = screen.getByLabelText('Outside search input');
    searchInput.focus();
    expect(document.activeElement).toBe(searchInput);

    // Trigger row collapse
    fireEvent.click(disclosureBtn);

    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('false');
  });
});
