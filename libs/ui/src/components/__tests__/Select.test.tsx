import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React, { createRef } from 'react';
import { NativeSelect, Select } from '../Select';

afterEach(cleanup);

describe('Select Component', () => {
  it('renders with options array correctly', () => {
    const handleChange = vi.fn();
    render(
      <Select
        aria-label="Test Select"
        value="opt2"
        onChange={handleChange}
        options={[
          { value: 'opt1', label: 'Option 1' },
          { value: 'opt2', label: 'Option 2' },
          { value: 'opt3', label: 'Option 3', disabled: true },
        ]}
      />,
    );

    const select = screen.getByRole('combobox', { name: 'Test Select' });
    expect(select).toBeDefined();
    expect((select as HTMLSelectElement).value).toBe('opt2');

    fireEvent.change(select, { target: { value: 'opt1' } });
    expect(handleChange).toHaveBeenCalled();
  });

  it('renders with children <option> correctly', () => {
    render(
      <Select aria-label="Status Select" defaultValue="ready">
        <option value="all">All</option>
        <option value="ready">Ready</option>
      </Select>,
    );

    const select = screen.getByRole('combobox', { name: 'Status Select' });
    expect((select as HTMLSelectElement).value).toBe('ready');
  });

  it('renders with stacked label, hint, and error', () => {
    const { rerender } = render(
      <Select
        label="Academic Program"
        hint="Select your department"
        required
        options={[{ value: 'bscs', label: 'Computer Science' }]}
      />,
    );

    expect(screen.getByText('Academic Program')).toBeDefined();
    expect(screen.getByText('*')).toBeDefined();
    expect(screen.getByText('Select your department')).toBeDefined();

    rerender(
      <Select
        label="Academic Program"
        error="Field is required"
        required
        options={[{ value: 'bscs', label: 'Computer Science' }]}
      />,
    );

    expect(screen.getByRole('alert').textContent).toContain('Field is required');
    const select = screen.getByRole('combobox');
    expect(select.getAttribute('aria-invalid')).toBe('true');
  });

  it('applies container classes once when a field wrapper is rendered', () => {
    const { container } = render(
      <Select
        label="Program"
        containerClassName="select-layout-marker"
        options={[{ value: 'bscs', label: 'Computer Science' }]}
      />,
    );

    expect(container.querySelectorAll('.select-layout-marker')).toHaveLength(1);
  });

  it('renders inline label layout correctly', () => {
    render(
      <Select
        label="Sort:"
        inlineLabel
        aria-label="Sort order"
        options={[{ value: 'asc', label: 'Ascending' }]}
      />,
    );

    expect(screen.getByText('Sort:')).toBeDefined();
    expect(screen.getByRole('combobox')).toBeDefined();
  });

  it('forwards ref to the underlying select element', () => {
    const ref = createRef<HTMLSelectElement>();
    render(
      <Select ref={ref} aria-label="Ref Test" options={[{ value: '1', label: 'One' }]} />,
    );

    expect(ref.current).toBeInstanceOf(HTMLSelectElement);
  });

  it('supports NativeSelect alias identically', () => {
    render(
      <NativeSelect aria-label="NativeSelect Alias" options={[{ value: 'a', label: 'A' }]} />,
    );

    expect(screen.getByRole('combobox', { name: 'NativeSelect Alias' })).toBeDefined();
  });
});
