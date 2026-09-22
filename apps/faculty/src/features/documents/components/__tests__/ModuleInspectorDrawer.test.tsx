// @vitest-environment jsdom
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ModuleInspectorDrawer } from '../ModuleInspectorDrawer';
import type { ClientDocument } from '@equiped/types';

// Mock @tanstack/react-router Link component
vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    className,
    'aria-label': ariaLabel,
  }: {
    children: React.ReactNode;
    to: string;
    className?: string;
    'aria-label'?: string;
  }) => (
    <a href={to} className={className} aria-label={ariaLabel}>
      {children}
    </a>
  ),
}));

const mockDocument: ClientDocument = {
  documentId: 'doc-abc-123',
  title: 'Data Structures and Algorithms SLM',
  courseTitle: 'Data Structures & Algorithms',
  lessonTitle: 'Module 3: Graph Traversal',
  sourceType: 'slm',
  program: 'BSCS',
  academicYear: '2026-2027',
  courseCode: 'CS 201',
  pageCount: 32,
  processingStatus: 'PROCESSED',
  hasOcrPages: false,
  uploadedAt: '2026-09-10T14:30:00.000Z',
  chunks: [],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ModuleInspectorDrawer Component', () => {
  it('does not render anything when document is null', () => {
    const { container } = render(
      <ModuleInspectorDrawer document={null} onClose={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders drawer dialog with title, status, program, and metadata specifications', () => {
    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    expect(
      screen.getByRole('dialog', {
        name: /Module details: Data Structures and Algorithms SLM/i,
      }),
    ).toBeDefined();

    expect(screen.getByText('Data Structures and Algorithms SLM')).toBeDefined();
    expect(screen.getAllByText(/Ready/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('BSCS').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('CS 201').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Data Structures & Algorithms')).toBeDefined();
    expect(screen.getByText('Module 3: Graph Traversal')).toBeDefined();
    expect(screen.getByText('2026-2027')).toBeDefined();
    expect(screen.getAllByText(/32 pages/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Searchable PDF')).toBeDefined();
  });

  it('renders only a single close control and has no duplicate footer close button', () => {
    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    // Header close button exists with accessible label
    const closeButtons = screen.getAllByRole('button', {
      name: /Close module details/i,
    });
    expect(closeButtons).toHaveLength(1);

    // There should NOT be a separate text button labeled "Close" in a footer
    const footerCloseBtn = screen.queryByRole('button', { name: /^Close$/i });
    expect(footerCloseBtn).toBeNull();
  });

  it('invokes onClose when clicking the header close button', () => {
    const handleClose = vi.fn();
    render(
      <ModuleInspectorDrawer document={mockDocument} onClose={handleClose} />,
    );

    const closeBtn = screen.getByRole('button', {
      name: /Close module details/i,
    });
    fireEvent.click(closeBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('invokes onClose when pressing Escape key', () => {
    const handleClose = vi.fn();
    render(
      <ModuleInspectorDrawer document={mockDocument} onClose={handleClose} />,
    );

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders direct PDF open action with correct URL and attributes', () => {
    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    const openPdfLink = screen.getByRole('link', { name: /Open PDF/i });
    expect(openPdfLink.getAttribute('href')).toBe(
      '/api/v1/documents/doc-abc-123/file',
    );
    expect(openPdfLink.getAttribute('target')).toBe('_blank');
    expect(openPdfLink.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('does NOT render dead outline or fabricated chunk count text when outline is missing', () => {
    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    // Tech-debt check: ensure fabricated messages like "0 searchable parts" or "No outline sections found" are eliminated
    expect(screen.queryByText(/0 searchable parts/i)).toBeNull();
    expect(screen.queryByText(/No outline sections found/i)).toBeNull();
    expect(screen.queryByText(/Module Outline/i)).toBeNull();
  });

  it('renders structured outline cleanly when real outline items exist', () => {
    const docWithOutline: ClientDocument = {
      ...mockDocument,
      structuredOutline: [
        {
          title: 'Unit 1: Introduction to Graphs',
          description: 'Vertices, edges, and representations',
        },
        {
          title: 'Unit 2: Depth-First Search',
          description: 'Recursion and traversal orders',
        },
      ],
    };

    render(
      <ModuleInspectorDrawer document={docWithOutline} onClose={vi.fn()} />,
    );

    expect(screen.getByText('Module outline')).toBeDefined();
    expect(screen.getByText('2 sections')).toBeDefined();
    expect(screen.getByText('Unit 1: Introduction to Graphs')).toBeDefined();
    expect(
      screen.getByText('Vertices, edges, and representations'),
    ).toBeDefined();
    expect(screen.getByText('Unit 2: Depth-First Search')).toBeDefined();
  });

  it('correctly handles scanned OCR document type and processing status', () => {
    const ocrDoc: ClientDocument = {
      ...mockDocument,
      hasOcrPages: true,
      processingStatus: 'PROCESSING',
    };

    render(<ModuleInspectorDrawer document={ocrDoc} onClose={vi.fn()} />);

    expect(screen.getByText('Scanned PDF')).toBeDefined();
    expect(screen.getAllByText('Processing').length).toBeGreaterThanOrEqual(1);
  });

  it('renders document summary with total pages, text format, and processing status', () => {
    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    expect(screen.getByText('Document information')).toBeDefined();
    expect(screen.getByText('Total pages')).toBeDefined();
    expect(screen.getByText('Text format')).toBeDefined();
    expect(screen.getByText('Processing status')).toBeDefined();
    expect(screen.getByText('Searchable PDF')).toBeDefined();
    expect(screen.getByText('Indexed')).toBeDefined();
    // Accreditation is removed from this summary section
    expect(screen.queryByText('Accreditation')).toBeNull();
  });

  it('renders multi-agent evaluation section with launch action when ready', () => {
    render(
      <ModuleInspectorDrawer
        document={mockDocument}
        targetAgent="sme"
        onClose={vi.fn()}
      />,
    );

    expect(
      screen.getByText('Multi-agent evaluation'),
    ).toBeDefined();
    expect(screen.getByRole('link', { name: /Launch Evaluation/i })).toBeDefined();
  });

  it('renders document file section and handles copy action for document ID', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(<ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />);

    expect(screen.getByText('Document file')).toBeDefined();
    expect(screen.getByText('doc-abc-123')).toBeDefined();

    const copyBtn = screen.getByRole('button', { name: /Copy document ID/i });
    fireEvent.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith('doc-abc-123');
    await waitFor(() => {
      expect(screen.getByText('Copied')).toBeDefined();
    });
  });

  it('displays "Not specified" for unavailable information instead of em-dashes', () => {
    const minimalDoc: ClientDocument = {
      ...mockDocument,
      pageCount: null,
      courseTitle: null,
      lessonTitle: null,
      academicYear: null,
      courseCode: null,
      program: null,
    };

    render(<ModuleInspectorDrawer document={minimalDoc} onClose={vi.fn()} />);

    const notSpecifiedElements = screen.getAllByText('Not specified');
    expect(notSpecifiedElements.length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText('—')).toBeNull();
  });

  it('displays human-readable module title as primary heading and filename as secondary', () => {
    const docWithFilename: ClientDocument = {
      ...mockDocument,
      title: 'BSCS_CMSC313_SLM1',
      courseTitle: 'Data Structures',
      lessonTitle: null,
    };

    render(<ModuleInspectorDrawer document={docWithFilename} onClose={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Data Structures' })).toBeDefined();
    expect(screen.getByText('BSCS_CMSC313_SLM1')).toBeDefined();
  });

  it('scopes copied feedback to the currently displayed document ID and does not leak across documents', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    const secondDoc: ClientDocument = {
      ...mockDocument,
      documentId: 'doc-xyz-789',
      title: 'Operating Systems SLM',
      courseTitle: 'Operating Systems',
    };

    const { rerender } = render(
      <ModuleInspectorDrawer document={mockDocument} onClose={vi.fn()} />,
    );

    const copyBtn = screen.getByRole('button', { name: /Copy document ID/i });
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(screen.getByText('Copied')).toBeDefined();
    });

    // Switch to another document: previous success state must not appear for the new document
    rerender(<ModuleInspectorDrawer document={secondDoc} onClose={vi.fn()} />);

    expect(screen.getByText('doc-xyz-789')).toBeDefined();
    expect(screen.queryByText('Copied')).toBeNull();
    expect(screen.getByRole('button', { name: /Copy document ID/i }).textContent).toContain('Copy');
  });
});
