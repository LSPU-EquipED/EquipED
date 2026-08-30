import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { DocumentDashboard } from '../DocumentDashboard';

// Mock dependencies
const mockUseDocumentDashboard = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ search: '?highlight=doc-1' }),
  Link: ({
    to,
    children,
    className,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock('../../hooks/useDocumentDashboard', () => ({
  useDocumentDashboard: () => mockUseDocumentDashboard(),
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe('DocumentDashboard', () => {
  const defaultDashboardState = {
    search: '',
    setSearch: vi.fn(),
    statusFilter: 'all',
    setStatusFilter: vi.fn(),
    page: 1,
    setPage: vi.fn(),
    pageSize: 10,
    setPageSize: vi.fn(),
    stats: { total: 2, ready: 1, processing: 1, failed: 0 },
    documents: [
      {
        documentId: 'doc-1',
        title: 'Network Systems Module',
        courseTitle: 'IT 201',
        program: 'BSInfoTech',
        sourceType: 'slm',
        uploadedAt: '2026-08-15T10:00:00Z',
        processingStatus: 'PROCESSED',
      },
      {
        documentId: 'doc-2',
        title: 'Database Admin Module',
        courseTitle: 'IT 202',
        program: 'BSInfoTech',
        sourceType: 'slm',
        uploadedAt: '2026-08-16T11:00:00Z',
        processingStatus: 'PENDING',
      },
    ],
    paginatedDocuments: [
      {
        documentId: 'doc-1',
        title: 'Network Systems Module',
        courseTitle: 'IT 201',
        program: 'BSInfoTech',
        sourceType: 'slm',
        uploadedAt: '2026-08-15T10:00:00Z',
        processingStatus: 'PROCESSED',
      },
      {
        documentId: 'doc-2',
        title: 'Database Admin Module',
        courseTitle: 'IT 202',
        program: 'BSInfoTech',
        sourceType: 'slm',
        uploadedAt: '2026-08-16T11:00:00Z',
        processingStatus: 'PENDING',
      },
    ],
    totalPages: 1,
    error: null,
    isLoading: false,
    isTableReady: true,
    data: { items: [], total: 2 },
  };

  it('renders a proper visible h1 and page intro for My SLMs', () => {
    mockUseDocumentDashboard.mockReturnValue(defaultDashboardState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toMatch(/<h1[^>]*>My SLMs<\/h1>/);
    expect(markup).toContain('Faculty Workspace');
    expect(markup).toContain('Manage your uploaded Self-Learning Modules');
  });

  it('renders flash success banner with accessible contrast colors', () => {
    mockUseDocumentDashboard.mockReturnValue(defaultDashboardState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain('Document uploaded successfully and is now available in My SLMs.');
    expect(markup).toContain('text-success');
    expect(markup).toContain('border-success/30');
    expect(markup).toContain('bg-success-soft');
    expect(markup).not.toContain('#3b963e');
  });

  it('renders exactly one in-page Upload SLM action in DocumentActionBar', () => {
    mockUseDocumentDashboard.mockReturnValue(defaultDashboardState);
    const markup = renderWithClient(<DocumentDashboard />);

    // Count occurrences of href="/upload" in the page
    const uploadMatches = markup.match(/href="\/upload"/g);
    expect(uploadMatches).toHaveLength(1);
    expect(markup).toContain('Upload SLM');
  });

  it('renders empty-state guidance pointing to the action bar without duplicate upload buttons', () => {
    mockUseDocumentDashboard.mockReturnValue({
      ...defaultDashboardState,
      stats: { total: 0, ready: 0, processing: 0, failed: 0 },
      documents: [],
      paginatedDocuments: [],
      data: { items: [], total: 0 },
    });
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain(
      'No SLMs uploaded yet. Use the Upload SLM button above to add course learning materials.',
    );
    // Still exactly one Upload SLM button in the entire page (in DocumentActionBar)
    const uploadMatches = markup.match(/href="\/upload"/g);
    expect(uploadMatches).toHaveLength(1);
  });
});
