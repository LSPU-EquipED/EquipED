// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ActionsMenu } from '../ActionsMenu';
import type { AnchorHTMLAttributes } from 'react';

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) => (
    <a href={to} {...props} />
  ),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function renderMenu() {
  const onDelete = vi.fn();
  render(
    <ActionsMenu
      name="Test Faculty"
      actions={[
        { label: 'Edit', icon: null, onSelect: vi.fn() },
        { label: 'Suspend', icon: null, onSelect: vi.fn(), disabled: true },
        {
          label: 'Delete',
          icon: null,
          onSelect: onDelete,
          destructive: true,
          separatorBefore: true,
        },
      ]}
    />,
  );
  return {
    trigger: screen.getByRole('button', { name: 'Actions for Test Faculty' }),
    onDelete,
  };
}

describe('ActionsMenu', () => {
  it('supports PDF and router links alongside commands, retaining menu keyboard navigation', () => {
    render(
      <ActionsMenu
        name="Module"
        actions={[
          { label: 'View details', icon: null, onSelect: vi.fn() },
          {
            label: 'Open PDF',
            icon: null,
            href: '/file.pdf',
            target: '_blank',
            rel: 'noopener noreferrer',
          },
          { label: 'Evaluate', icon: null, to: '/specialists/sme/module' },
        ]}
      />,
    );
    const trigger = screen.getByRole('button', { name: 'Actions for Module' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const details = screen.getByRole('menuitem', { name: 'View details' });
    const pdf = screen.getByRole('menuitem', { name: 'Open PDF' });
    const evaluate = screen.getByRole('menuitem', { name: 'Evaluate' });
    fireEvent.keyDown(details, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(pdf);
    fireEvent.keyDown(pdf, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(evaluate);
    expect(pdf.getAttribute('href')).toBe('/file.pdf');
    expect(pdf.getAttribute('target')).toBe('_blank');
    expect(evaluate.getAttribute('href')).toBe('/specialists/sme/module');
    fireEvent.click(pdf);
    expect(screen.queryByRole('menu')).toBeNull();
  });
  it('renders outside the table and positions above the trigger near the viewport edge', () => {
    vi.stubGlobal('innerWidth', 390);
    vi.stubGlobal('innerHeight', 844);
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(176);
    vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(192);
    const { trigger } = renderMenu();
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({
      x: 350,
      y: 780,
      top: 780,
      bottom: 820,
      left: 350,
      right: 390,
      width: 40,
      height: 40,
      toJSON: () => ({}),
    });
    fireEvent.click(trigger);
    const menu = screen.getByRole('menu');
    expect(menu.parentElement).toBe(document.body);
    expect(menu.style.position).toBe('fixed');
    expect(menu.style.top).toBe('596px');
    expect(menu.style.left).toBe('190px');
  });
  it('opens on click and closes after selecting a command, restoring trigger focus', () => {
    const { trigger, onDelete } = renderMenu();
    expect(screen.queryByRole('menu')).toBeNull();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(onDelete).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('supports arrow keys, Home, End, and Escape while skipping disabled commands', () => {
    const { trigger } = renderMenu();
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const edit = screen.getByRole('menuitem', { name: 'Edit' });
    const remove = screen.getByRole('menuitem', { name: 'Delete' });
    expect(document.activeElement).toBe(edit);
    fireEvent.keyDown(edit, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(remove);
    fireEvent.keyDown(remove, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(edit);
    fireEvent.keyDown(edit, { key: 'End' });
    expect(document.activeElement).toBe(remove);
    fireEvent.keyDown(remove, { key: 'Home' });
    expect(document.activeElement).toBe(edit);
    fireEvent.keyDown(edit, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('opens at the last enabled command with ArrowUp and dismisses with Tab', () => {
    const { trigger } = renderMenu();
    fireEvent.keyDown(trigger, { key: 'ArrowUp' });
    const remove = screen.getByRole('menuitem', { name: 'Delete' });
    expect(document.activeElement).toBe(remove);
    fireEvent.keyDown(remove, { key: 'Tab' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('dismisses on outside clicks and never invokes disabled commands', () => {
    const { trigger, onDelete } = renderMenu();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Suspend' }));
    expect(screen.getByRole('menu')).toBeDefined();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
    expect(onDelete).not.toHaveBeenCalled();
  });
});
