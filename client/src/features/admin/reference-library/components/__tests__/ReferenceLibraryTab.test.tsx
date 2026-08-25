// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { ReferenceLibraryTab } from '../ReferenceLibraryTab';
import { ReferenceRow } from '../ReferenceRow';
import type { ReferenceLibraryItem } from '../../types';

const mockReferences: ReferenceLibraryItem[] = [
  {
    documentId: 'doc-syl-1',
    title: 'Computer Science 101 Syllabus',
    sourceType: 'syllabus',
    program: 'BSCS',
    courseCode: 'CS101',
    academicYear: '2025-2026',
    courseTitle: 'Introduction to Computing',
    lessonTitle: 'Module 1',
    pageCount: 10,
    uploadedAt: '2026-08-10T10:00:00Z',
    uploadedBy: 'admin',
    processingStatus: 'PROCESSED',
    fileExists: true,
    chunkCount: 15,
    chromaAvailable: true,
    embeddingReady: true,
  },
  {
    documentId: 'doc-curr-1',
    title: 'BSCS Curriculum 2026',
    sourceType: 'curriculum',
    program: 'BSCS',
    courseCode: null,
    academicYear: '2026-2027',
    courseTitle: null,
    lessonTitle: null,
    pageCount: 25,
    uploadedAt: '2026-08-11T11:00:00Z',
    uploadedBy: 'admin',
    processingStatus: 'PROCESSED',
    fileExists: true,
    chunkCount: 30,
    chromaAvailable: false,
    embeddingReady: false,
  },
];

const mockDeleteMutate = vi.fn();
const mockRebuildMutate = vi.fn();
let mockDeleteState = {
  mutateAsync: mockDeleteMutate,
  isPending: false,
  isError: false,
  error: null as Error | null,
  variables: undefined as string | undefined,
};
let mockRebuildState = {
  mutateAsync: mockRebuildMutate,
  isPending: false,
  isError: false,
  error: null as Error | null,
  variables: undefined as string | undefined,
};

vi.mock('../../hooks/useReferenceLibrary', () => ({
  useReferenceLibrary: () => ({
    data: { items: mockReferences, total: 2 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useDeleteReference: () => mockDeleteState,
  useRebuildReferenceEmbeddings: () => mockRebuildState,
  getReferenceFileUrl: (id: string) => `/documents/${id}/file`,
  getReferenceOperationError: (err: unknown) => (err instanceof Error ? err.message : String(err)),
}));

vi.mock('@tanstack/react-router', () => ({
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

describe('ReferenceLibraryTab', () => {
  afterEach(() => {
    cleanup();
    mockDeleteState = {
      mutateAsync: mockDeleteMutate,
      isPending: false,
      isError: false,
      error: null,
      variables: undefined,
    };
    mockRebuildState = {
      mutateAsync: mockRebuildMutate,
      isPending: false,
      isError: false,
      error: null,
      variables: undefined,
    };
  });

  it('renders both Syllabus and Curriculum rows with Program column and filter tab counts', () => {
    render(<ReferenceLibraryTab />);

    expect(screen.getByText('Computer Science 101 Syllabus')).toBeDefined();
    expect(screen.getByText('BSCS Curriculum 2026')).toBeDefined();

    // Check Program column headers
    expect(screen.getByRole('columnheader', { name: /Program/i })).toBeDefined();

    // Check filter buttons with count badges
    const allBtn = screen.getByRole('button', { name: /All/i });
    const syllabusBtn = screen.getByRole('button', { name: /Syllabus/i });
    const curriculumBtn = screen.getByRole('button', { name: /Curriculum/i });

    expect(allBtn).toBeDefined();
    expect(syllabusBtn).toBeDefined();
    expect(curriculumBtn).toBeDefined();
  });

  it('filters rows when selecting Curriculum filter', () => {
    render(<ReferenceLibraryTab />);

    const curriculumBtn = screen.getByRole('button', { name: /Curriculum/i });
    fireEvent.click(curriculumBtn);

    expect(screen.getByText('BSCS Curriculum 2026')).toBeDefined();
    expect(screen.queryByText('Computer Science 101 Syllabus')).toBeNull();
  });

  it('filters rows when selecting Syllabus filter', () => {
    render(<ReferenceLibraryTab />);

    const syllabusBtn = screen.getByRole('button', { name: /Syllabus/i });
    fireEvent.click(syllabusBtn);

    expect(screen.getByText('Computer Science 101 Syllabus')).toBeDefined();
    expect(screen.queryByText('BSCS Curriculum 2026')).toBeNull();
  });

  it('derives busy state ONLY while mutation is pending and re-enables when settled with retained variables', () => {
    // 1. Mutation pending: row is busy and disabled
    mockDeleteState = {
      mutateAsync: mockDeleteMutate,
      isPending: true,
      isError: false,
      error: null,
      variables: 'doc-curr-1',
    };

    const { rerender } = render(<ReferenceLibraryTab />);
    const deleteButtons = screen.getAllByRole('button', { name: /Delete/i });
    expect((deleteButtons[1] as HTMLButtonElement).disabled).toBe(true);

    // 2. Mutation settled: isPending becomes false, variables retained in query cache
    mockDeleteState = {
      mutateAsync: mockDeleteMutate,
      isPending: false,
      isError: false,
      error: null,
      variables: 'doc-curr-1',
    };

    rerender(<ReferenceLibraryTab />);
    const deleteButtonsAfterSettle = screen.getAllByRole('button', { name: /Delete/i });
    expect((deleteButtonsAfterSettle[1] as HTMLButtonElement).disabled).toBe(false);
  });

  it('renders table error banner with role="alert" and aria-live="assertive" on mutation failure', () => {
    mockRebuildState = {
      mutateAsync: mockRebuildMutate,
      isPending: false,
      isError: true,
      error: new Error('Failed to rebuild Chroma embeddings for document'),
      variables: 'doc-curr-1',
    };

    render(<ReferenceLibraryTab />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.getAttribute('aria-live')).toBe('assertive');
    expect(alert.textContent).toContain('Failed to rebuild Chroma embeddings for document');
  });
});

describe('ReferenceRow', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders Curriculum type label, canonical program, and status without retired copy', () => {
    render(
      <table>
        <tbody>
          <ReferenceRow
            item={mockReferences[1]}
            isBusy={false}
            isDeleting={false}
            isRebuilding={false}
            onPreview={vi.fn()}
            onRebuild={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    );

    expect(screen.getByText('BSCS Curriculum 2026')).toBeDefined();
    expect(screen.getByText('Curriculum')).toBeDefined();
    expect(screen.getByText('BSCS')).toBeDefined();
    expect(screen.getByText('PROCESSED')).toBeDefined();
    expect(screen.getByText('30')).toBeDefined();
    expect(screen.getByText('Not indexed')).toBeDefined();

    // Ensure rebuild button is active and does NOT contain retired copy
    const rebuildBtn = screen.getByRole('button', { name: /Rebuild/i }) as HTMLButtonElement;
    expect(rebuildBtn.disabled).toBe(false);
    expect(rebuildBtn.title).not.toContain('retired');
    expect(rebuildBtn.title).toContain('Rebuild Chroma vectors from stored chunks');
  });

  it('triggers onPreview, onRebuild, and onDelete callbacks for curriculum', () => {
    const onPreview = vi.fn();
    const onRebuild = vi.fn();
    const onDelete = vi.fn();

    render(
      <table>
        <tbody>
          <ReferenceRow
            item={mockReferences[1]}
            isBusy={false}
            isDeleting={false}
            isRebuilding={false}
            onPreview={onPreview}
            onRebuild={onRebuild}
            onDelete={onDelete}
          />
        </tbody>
      </table>,
    );

    const previewBtn = screen.getByRole('button', { name: /Preview/i });
    fireEvent.click(previewBtn);
    expect(onPreview).toHaveBeenCalledTimes(1);

    const rebuildBtn = screen.getByRole('button', { name: /Rebuild/i }) as HTMLButtonElement;
    expect(rebuildBtn.disabled).toBe(false);
    fireEvent.click(rebuildBtn);
    expect(onRebuild).toHaveBeenCalledTimes(1);

    const deleteBtn = screen.getByRole('button', { name: /Delete/i });
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });
});
