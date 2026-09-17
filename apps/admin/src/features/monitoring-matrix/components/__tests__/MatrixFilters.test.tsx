// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
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
});
