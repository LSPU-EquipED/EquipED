// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React, { useState } from 'react';
import { MatrixFilters } from '../MatrixFilters';

afterEach(cleanup);

describe('MatrixFilters', () => {
  it('renders exactly the two canonical program options', () => {
    render(
      <MatrixFilters
        program="all"
        status="all"
        onProgramChange={vi.fn()}
        onStatusChange={vi.fn()}
      />,
    );

    const programTrigger = screen.getByRole('button', { name: 'Filter by program' });
    expect(programTrigger).toBeDefined();

    fireEvent.click(programTrigger);

    const options = screen.getAllByRole('option');
    const optionLabels = options.map((opt) => opt.textContent?.trim());

    expect(optionLabels).toContain('All Programs');
    expect(optionLabels).toContain('Computer Science');
    expect(optionLabels).toContain('Information Technology');
    expect(optionLabels).not.toContain('Education');
  });

  it('emits BSInfoTech when Information Technology is selected', () => {
    const onProgramChange = vi.fn();
    render(
      <MatrixFilters
        program="all"
        status="all"
        onProgramChange={onProgramChange}
        onStatusChange={vi.fn()}
      />,
    );

    const programTrigger = screen.getByRole('button', { name: 'Filter by program' });
    fireEvent.click(programTrigger);

    const infoTechOption = screen.getByRole('option', { name: /Information Technology/i });
    fireEvent.click(infoTechOption);

    expect(onProgramChange).toHaveBeenCalledWith('BSInfoTech');
  });

  it('focuses search input when Clear search button is clicked and unmounted after rerender', () => {
    function ControlledFilters() {
      const [searchQuery, setSearchQuery] = useState('react');
      return (
        <MatrixFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          program="all"
          status="all"
          onProgramChange={vi.fn()}
          onStatusChange={vi.fn()}
        />
      );
    }

    render(<ControlledFilters />);

    const searchInput = screen.getByLabelText('Search monitoring matrix');
    const clearButton = screen.getByLabelText('Clear search');

    expect(clearButton).not.toBeNull();
    fireEvent.click(clearButton);

    expect(screen.queryByLabelText('Clear search')).toBeNull();
    expect(document.activeElement).toBe(searchInput);
  });

  it('focuses search input when Reset button is clicked and unmounted after rerender', () => {
    function ControlledFilters() {
      const [searchQuery, setSearchQuery] = useState('react');
      const [program, setProgram] = useState('BSCS');
      const [status, setStatus] = useState('IN_PROGRESS');

      return (
        <MatrixFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          program={program}
          status={status}
          onProgramChange={setProgram}
          onStatusChange={setStatus}
          onResetFilters={() => {
            setSearchQuery('');
            setProgram('all');
            setStatus('all');
          }}
        />
      );
    }

    render(<ControlledFilters />);

    const searchInput = screen.getByLabelText('Search monitoring matrix');
    const resetButton = screen.getByRole('button', { name: /reset/i });

    expect(resetButton).not.toBeNull();
    fireEvent.click(resetButton);

    expect(screen.queryByRole('button', { name: /reset/i })).toBeNull();
    expect(document.activeElement).toBe(searchInput);
  });
});
