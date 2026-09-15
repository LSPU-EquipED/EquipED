import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { DocumentDashboard } from '../DocumentDashboard';

// Mock dependencies
const mockUseSlmStorage = vi.fn();

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

vi.mock('../../hooks/useSlmStorage', () => ({
  useSlmStorage: () => mockUseSlmStorage(),
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

describe('DocumentDashboard - SLM Storage Repository', () => {
  const defaultStorageState = {
    search: '',
    setSearch: vi.fn(),
    programFilter: 'ALL',
    setProgramFilter: vi.fn(),
    statusFilter: 'all',
    setStatusFilter: vi.fn(),
    page: 1,
    setPage: vi.fn(),
    pageSize: 10,
    setPageSize: vi.fn(),
    total: 2,
    totalPages: 1,
    metrics: {
      totalModules: 2,
      totalIndexedPages: 45,
      bscsCount: 1,
      bsInfoTechCount: 1,
      ocrVerifiedCount: 1,
    },
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
        pageCount: 25,
        hasOcrPages: true,
      },
      {
        documentId: 'doc-2',
        title: 'Database Admin Module',
        courseTitle: 'IT 202',
        program: 'BSInfoTech',
        sourceType: 'slm',
        uploadedAt: '2026-08-16T11:00:00Z',
        processingStatus: 'PENDING',
        pageCount: 20,
        hasOcrPages: false,
      },
    ],
    error: null,
    isLoading: false,
    inspectingDoc: null,
    setInspectingDoc: vi.fn(),
    isUploadOpen: false,
    setIsUploadOpen: vi.fn(),
    evaluatingTarget: null,
    setEvaluatingTarget: vi.fn(),
    handleUploadComplete: vi.fn(),
  };

  it('renders SLM storage metrics strip and table', () => {
    mockUseSlmStorage.mockReturnValue(defaultStorageState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain('Course Modules');
    expect(markup).toContain('Indexed Content');
    expect(markup).toContain('Network Systems Module');
    expect(markup).toContain('Upload SLM');
  });

  it('renders flash success banner with accessible contrast colors', () => {
    mockUseSlmStorage.mockReturnValue(defaultStorageState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain('Document uploaded successfully and is now indexed in SLM Storage.');
    expect(markup).toContain('text-success');
    expect(markup).toContain('border-success/30');
    expect(markup).toContain('bg-success-soft');
  });

  it('renders empty state guidance when no modules exist in storage', () => {
    mockUseSlmStorage.mockReturnValue({
      ...defaultStorageState,
      total: 0,
      metrics: {
        totalModules: 0,
        totalIndexedPages: 0,
        bscsCount: 0,
        bsInfoTechCount: 0,
        ocrVerifiedCount: 0,
      },
      stats: { total: 0, ready: 0, processing: 0, failed: 0 },
      documents: [],
    });
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain('No SLMs in Storage Yet');
    expect(markup).toContain('Upload course learning modules in PDF format');
  });
});
