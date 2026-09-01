import { describe, expect, it, vi } from 'vitest';
import { MatrixFilters } from '../MatrixFilters';

describe('MatrixFilters', () => {
  it('renders exactly the two canonical program options', () => {
    const element = MatrixFilters({
      program: 'all',
      status: 'all',
      onProgramChange: vi.fn(),
      onStatusChange: vi.fn(),
    });
    const programSelect = element.props.children[0].props.children;
    const options = programSelect.props.children;

    expect(
      options.map((option: { props: { children: string; value: string } }) => [
        option.props.children,
        option.props.value,
      ]),
    ).toEqual([
      ['All Programs', 'all'],
      ['Computer Science', 'BSCS'],
      ['Information Technology', 'BSInfoTech'],
    ]);
    expect(
      options.map((option: { props: { children: string } }) => option.props.children),
    ).not.toContain('Education');
  });

  it('emits BSInfoTech when Information Technology is selected', () => {
    const onProgramChange = vi.fn();
    const element = MatrixFilters({
      program: 'all',
      status: 'all',
      onProgramChange,
      onStatusChange: vi.fn(),
    });
    const programSelect = element.props.children[0].props.children;

    programSelect.props.onChange({ target: { value: 'BSInfoTech' } });

    expect(onProgramChange).toHaveBeenCalledWith('BSInfoTech');
  });
});
