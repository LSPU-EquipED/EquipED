// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import React from 'react';
import { CollapsibleRow } from '../CollapsibleRow';

describe('CollapsibleRow', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders collapsed state with inert and aria-hidden on animated container', () => {
    render(
      <table>
        <tbody>
          <CollapsibleRow isExpanded={false} colSpan={4}>
            <div>
              <a href="/test-link">Hidden Link</a>
              <button type="button">Hidden Button</button>
            </div>
          </CollapsibleRow>
        </tbody>
      </table>,
    );

    const animatedContainer = document.querySelector('.animate-ledger-collapse');
    expect(animatedContainer).not.toBeNull();
    expect(animatedContainer?.getAttribute('aria-hidden')).toBe('true');
    expect(animatedContainer?.hasAttribute('inert')).toBe(true);
    expect(animatedContainer?.className).toContain('animate-ledger-collapse-collapsed');
  });

  it('renders expanded state without inert and aria-hidden is false', () => {
    render(
      <table>
        <tbody>
          <CollapsibleRow isExpanded={true} colSpan={4}>
            <div>
              <a href="/test-link">Visible Link</a>
              <button type="button">Visible Button</button>
            </div>
          </CollapsibleRow>
        </tbody>
      </table>,
    );

    const animatedContainer = document.querySelector('.animate-ledger-collapse');
    expect(animatedContainer).not.toBeNull();
    expect(animatedContainer?.getAttribute('aria-hidden')).toBe('false');
    expect(animatedContainer?.hasAttribute('inert')).toBe(false);
    expect(animatedContainer?.className).toContain('animate-ledger-collapse-expanded');

    // Children are reachable and findable via role queries
    expect(screen.getByRole('link', { name: 'Visible Link' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Visible Button' })).toBeDefined();
  });

  it('preserves children and custom class names across states', () => {
    const { rerender } = render(
      <table>
        <tbody>
          <CollapsibleRow
            isExpanded={false}
            colSpan={3}
            className="custom-row"
            cellClassName="custom-cell"
            innerClassName="custom-inner"
          >
            <span>Drawer content</span>
          </CollapsibleRow>
        </tbody>
      </table>,
    );

    const row = document.querySelector('tr');
    const cell = document.querySelector('td');
    const inner = document.querySelector('.custom-inner');

    expect(row?.className).toContain('custom-row');
    expect(cell?.className).toContain('custom-cell');
    expect(inner?.textContent).toBe('Drawer content');

    rerender(
      <table>
        <tbody>
          <CollapsibleRow
            isExpanded={true}
            colSpan={3}
            className="custom-row"
            cellClassName="custom-cell"
            innerClassName="custom-inner"
          >
            <span>Drawer content</span>
          </CollapsibleRow>
        </tbody>
      </table>,
    );

    expect(row?.className).toContain('custom-row');
    expect(inner?.textContent).toBe('Drawer content');
  });
});
