import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentPagination } from '../DocumentPagination';

describe('DocumentPagination', () => {
  it('renders accessible pagination navigation with aria-label', () => {
    const markup = renderToStaticMarkup(
      <DocumentPagination
        page={1}
        setPage={vi.fn()}
        pageSize={10}
        setPageSize={vi.fn()}
        totalPages={5}
      />,
    );

    expect(markup).toContain('<nav aria-label="Pagination"');
    expect(markup).toContain('aria-label="Previous page"');
    expect(markup).toContain('aria-label="Next page"');
  });

  it('sets aria-current="page" on the active page and aria-label on numbered pages', () => {
    const markup = renderToStaticMarkup(
      <DocumentPagination
        page={2}
        setPage={vi.fn()}
        pageSize={10}
        setPageSize={vi.fn()}
        totalPages={3}
      />,
    );

    expect(markup).toContain('aria-label="Page 1"');
    expect(markup).toContain('aria-label="Page 2"');
    expect(markup).toContain('aria-label="Page 3"');
    // Button 2 is current
    expect(markup).toMatch(/aria-label="Page 2"[^>]*aria-current="page"/);
    // Button 1 is not current
    expect(markup).not.toMatch(/aria-label="Page 1"[^>]*aria-current="page"/);
  });

  it('disables previous button on first page and next button on last page', () => {
    const page1Markup = renderToStaticMarkup(
      <DocumentPagination
        page={1}
        setPage={vi.fn()}
        pageSize={10}
        setPageSize={vi.fn()}
        totalPages={3}
      />,
    );
    expect(page1Markup).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Previous page"/);

    const page3Markup = renderToStaticMarkup(
      <DocumentPagination
        page={3}
        setPage={vi.fn()}
        pageSize={10}
        setPageSize={vi.fn()}
        totalPages={3}
      />,
    );
    expect(page3Markup).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Next page"/);
  });

  it('renders dots with aria-hidden="true" and accessible text-text-muted class when totalPages > 5', () => {
    const markup = renderToStaticMarkup(
      <DocumentPagination
        page={5}
        setPage={vi.fn()}
        pageSize={10}
        setPageSize={vi.fn()}
        totalPages={10}
      />,
    );

    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain('text-text-muted');
  });

  it('renders page size selector with accessible label and options', () => {
    const markup = renderToStaticMarkup(
      <DocumentPagination
        page={1}
        setPage={vi.fn()}
        pageSize={25}
        setPageSize={vi.fn()}
        totalPages={4}
      />,
    );

    expect(markup).toContain('aria-label="Rows per page"');
    expect(markup).toContain('id="document-page-size"');
    expect(markup).toContain('for="document-page-size"');
  });
});
