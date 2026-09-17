import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React, { createRef } from 'react';
import { Dropdown } from '../Dropdown';

afterEach(cleanup);

describe('Dropdown Component', () => {
  const defaultOptions = [
    { value: 'opt1', label: 'Option 1' },
    { value: 'opt2', label: 'Option 2' },
    { value: 'opt3', label: 'Option 3', disabled: true },
  ];

  it('renders trigger with selected value label', () => {
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt2"
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    expect(trigger).toBeDefined();
    expect(trigger.textContent).toContain('Option 2');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('opens popup menu on click, moves focus to listbox, and lists options', () => {
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');

    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeDefined();
    expect(document.activeElement).toBe(listbox);

    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(3);
    expect(options[0].getAttribute('aria-selected')).toBe('true');
    expect(options[1].getAttribute('aria-selected')).toBe('false');
    expect(options[2].getAttribute('aria-disabled')).toBe('true');
  });

  it('moves focus to listbox when opened via keyboard and restores focus to trigger on Escape', () => {
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeDefined();
    expect(document.activeElement).toBe(listbox);

    fireEvent.keyDown(listbox, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('restores focus to trigger when an option is selected', () => {
    const handleChange = vi.fn();
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        onChange={handleChange}
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    fireEvent.click(trigger);

    const option2 = screen.getByRole('option', { name: 'Option 2' });
    fireEvent.click(option2);

    expect(handleChange).toHaveBeenCalledWith('opt2');
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('closes when clicking outside container', () => {
    render(
      <div>
        <Dropdown
          aria-label="Test Dropdown"
          value="opt1"
          options={defaultOptions}
        />
        <button type="button">Outside Element</button>
      </div>,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    fireEvent.click(trigger);
    expect(screen.getByRole('listbox')).toBeDefined();

    const outsideButton = screen.getByRole('button', { name: /Outside Element/i });
    fireEvent.mouseDown(outsideButton);

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('calls onChange and closes when an option is selected', () => {
    const handleChange = vi.fn();
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        onChange={handleChange}
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    fireEvent.click(trigger);

    const option2 = screen.getByRole('option', { name: 'Option 2' });
    fireEvent.click(option2);

    expect(handleChange).toHaveBeenCalledWith('opt2');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('does not select disabled options on click', () => {
    const handleChange = vi.fn();
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        onChange={handleChange}
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    fireEvent.click(trigger);

    const option3 = screen.getByRole('option', { name: 'Option 3' });
    fireEvent.click(option3);

    expect(handleChange).not.toHaveBeenCalled();
    expect(screen.getByRole('listbox')).toBeDefined();
  });

  it('closes on Escape key and returns focus to trigger', () => {
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    fireEvent.click(trigger);
    expect(screen.getByRole('listbox')).toBeDefined();

    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('supports keyboard navigation (ArrowDown, Enter)', () => {
    const handleChange = vi.fn();
    render(
      <Dropdown
        aria-label="Test Dropdown"
        value="opt1"
        onChange={handleChange}
        options={defaultOptions}
      />,
    );

    const trigger = screen.getByRole('button', { name: /Test Dropdown/i });
    // Open via ArrowDown
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeDefined();

    // Navigate to next option
    fireEvent.keyDown(listbox, { key: 'ArrowDown' });
    // Select via Enter
    fireEvent.keyDown(listbox, { key: 'Enter' });

    expect(handleChange).toHaveBeenCalledWith('opt2');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('renders inline label correctly', () => {
    render(
      <Dropdown
        label="Sort:"
        inlineLabel
        value="opt1"
        options={defaultOptions}
      />,
    );

    expect(screen.getByText('Sort:')).toBeDefined();
    const trigger = screen.getByRole('button');
    expect(trigger.textContent).toContain('Option 1');
  });

  it('forwards ref to trigger button', () => {
    const ref = createRef<HTMLButtonElement>();
    render(
      <Dropdown
        ref={ref}
        aria-label="Ref Test"
        options={defaultOptions}
      />,
    );

    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });
});
