import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { StorageToolbar } from '../StorageToolbar';

describe('StorageToolbar Component', () => {
  it('renders module counts consistently in all tabs including 0 count', () => {
    const markup = renderToStaticMarkup(
      <StorageToolbar
        programFilter="ALL"
        setProgramFilter={vi.fn()}
        statusFilter="all"
        setStatusFilter={vi.fn()}
        totalModules={5}
        bscsCount={5}
        bsInfoTechCount={0}
      />,
    );

    expect(markup).toContain('All Modules');
    expect(markup).toContain('5');
    expect(markup).toContain('BSCS');
    expect(markup).toContain('BSInfoTech');
    // Verifies that BSInfoTech 0 count is explicitly rendered instead of hidden
    expect(markup).toContain('0');
  });

  it('highlights the active program filter tab with primary background', () => {
    const markup = renderToStaticMarkup(
      <StorageToolbar
        programFilter="BSCS"
        setProgramFilter={vi.fn()}
        statusFilter="all"
        setStatusFilter={vi.fn()}
        totalModules={10}
        bscsCount={10}
        bsInfoTechCount={0}
      />,
    );

    expect(markup).toContain('bg-primary text-primary-foreground');
  });

  it('renders reset filter button when a filter is active', () => {
    const markup = renderToStaticMarkup(
      <StorageToolbar
        programFilter="BSInfoTech"
        setProgramFilter={vi.fn()}
        statusFilter="all"
        setStatusFilter={vi.fn()}
        onResetFilters={vi.fn()}
      />,
    );

    expect(markup).toContain('Reset');
  });
});
