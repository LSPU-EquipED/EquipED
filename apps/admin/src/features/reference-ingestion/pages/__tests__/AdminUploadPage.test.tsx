// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { documentsApi } from '@/shared/api/documents.api';
import type { ClientDocument } from '@/shared/types/documents';
import { AdminUploadPage } from '../AdminUploadPage';

const mockUploadDocument = vi.fn();
const mockResetData = vi.fn();
let mockErrorMessage: string | null = null;

vi.mock('../../hooks/useAdminUpload', () => ({
  useAdminUpload: () => {
    const [, forceUpdate] = React.useState(0);
    return {
      uploadDocument: async (...args: unknown[]) => {
        try {
          return await mockUploadDocument(...args);
        } catch (err) {
          mockErrorMessage = err instanceof Error ? err.message : String(err);
          forceUpdate((n) => n + 1);
          throw err;
        }
      },
      isLoading: false,
      errorMessage: mockErrorMessage,
      setData: mockResetData,
    };
  },
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

describe('AdminUploadPage', () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    mockErrorMessage = null;
    vi.clearAllMocks();
  });

  it('renders all document type options including Curriculum, Syllabus, and Policy', () => {
    render(<AdminUploadPage />);

    expect(screen.getByLabelText(/Document Type/i)).toBeDefined();
    expect(screen.getByRole('option', { name: 'Syllabus' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Curriculum' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Policy' })).toBeDefined();
  });

  it('renders ProgramSelector when Curriculum is selected', () => {
    render(<AdminUploadPage />);

    const select = screen.getByLabelText(/Document Type/i);
    fireEvent.change(select, { target: { value: 'curriculum' } });

    expect(screen.getByRole('button', { name: /Program/i })).toBeDefined();
    expect(screen.getByText(/Required for curriculum references/i)).toBeDefined();
  });

  it('resets program and policyArea when switching source type', () => {
    render(<AdminUploadPage />);

    const select = screen.getByLabelText(/Document Type/i);

    // Switch to curriculum
    fireEvent.change(select, { target: { value: 'curriculum' } });
    expect(screen.getByRole('button', { name: /Program/i })).toBeDefined();

    // Switch to policy
    fireEvent.change(select, { target: { value: 'policy' } });
    expect(screen.queryByRole('button', { name: /Program/i })).toBeNull();
    expect(screen.getByLabelText(/Policy Area/i)).toBeDefined();

    // Switch back to syllabus
    fireEvent.change(select, { target: { value: 'syllabus' } });
    expect(screen.queryByLabelText(/Policy Area/i)).toBeNull();
    expect(screen.queryByRole('button', { name: /Program/i })).toBeNull();
  });

  it('disables submit button when Curriculum is selected without a program', () => {
    render(<AdminUploadPage />);

    const titleInput = screen.getByLabelText(/Title/i);
    fireEvent.change(titleInput, { target: { value: 'BSCS Curriculum 2026' } });

    const typeSelect = screen.getByLabelText(/Document Type/i);
    fireEvent.change(typeSelect, { target: { value: 'curriculum' } });

    const submitBtn = screen.getByRole('button', { name: /Ingest document/i }) as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);
  });

  it('displays first processing warning when background ingestion fails', async () => {
    mockUploadDocument.mockResolvedValue({
      documentId: 'doc-fail-1',
      title: 'Failed Curriculum',
      sourceType: 'curriculum',
      processingStatus: 'PROCESSING',
      program: 'BSCS',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    });

    const mockFailedDoc: ClientDocument = {
      documentId: 'doc-fail-1',
      title: 'Failed Curriculum',
      sourceType: 'curriculum',
      program: 'BSCS',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
      pageCount: 5,
      processingStatus: 'FAILED',
      hasOcrPages: true,
      uploadedAt: '2026-08-24T10:00:00Z',
      processingWarnings: ['OCR processing error on page 3: Degraded scanned resolution'],
      chunks: [],
    };

    const getDocSpy = vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockFailedDoc);

    render(<AdminUploadPage />);

    const file = new File(['dummy content'], 'curriculum.pdf', { type: 'application/pdf' });
    const fileInput = screen.getByLabelText(/Drop a PDF here/i);
    fireEvent.change(fileInput, { target: { files: [file] } });

    const typeSelect = screen.getByLabelText(/Document Type/i);
    fireEvent.change(typeSelect, { target: { value: 'curriculum' } });

    const programBtn = screen.getByRole('button', { name: /Program/i });
    fireEvent.click(programBtn);
    const bscsOption = screen.getByRole('option', { name: /BSCS/i });
    fireEvent.click(bscsOption);

    const submitBtn = screen.getByRole('button', { name: /Ingest document/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('OCR processing error on page 3: Degraded scanned resolution')).toBeDefined();
    });

    const alertBox = screen.getByRole('alert');
    expect(alertBox.getAttribute('aria-live')).toBe('assertive');
    expect(screen.getByText('Failed')).toBeDefined();

    getDocSpy.mockRestore();
  });

  it('displays truthful generic fallback error when background ingestion fails without warnings', async () => {
    mockUploadDocument.mockResolvedValue({
      documentId: 'doc-fail-2',
      title: 'Failed Syllabus',
      sourceType: 'syllabus',
      processingStatus: 'PROCESSING',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    });

    const mockFailedDoc: ClientDocument = {
      documentId: 'doc-fail-2',
      title: 'Failed Syllabus',
      sourceType: 'syllabus',
      program: null,
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
      pageCount: 5,
      processingStatus: 'FAILED',
      hasOcrPages: false,
      uploadedAt: '2026-08-24T10:00:00Z',
      processingWarnings: [],
      chunks: [],
    };

    const getDocSpy = vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockFailedDoc);

    render(<AdminUploadPage />);

    const file = new File(['dummy content'], 'syllabus.pdf', { type: 'application/pdf' });
    const fileInput = screen.getByLabelText(/Drop a PDF here/i);
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Ingest document/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Document processing failed. Please verify the uploaded reference and try again.')).toBeDefined();
    });

    const alertBox = screen.getByRole('alert');
    expect(alertBox.getAttribute('aria-live')).toBe('assertive');
    expect(screen.getByText('Failed')).toBeDefined();

    getDocSpy.mockRestore();
  });

  it('displays immediate failure alert when uploadDocument rejects before background task', async () => {
    mockUploadDocument.mockRejectedValue(new Error('File upload rejected: storage quota exceeded.'));

    render(<AdminUploadPage />);

    const file = new File(['dummy content'], 'syllabus.pdf', { type: 'application/pdf' });
    const fileInput = screen.getByLabelText(/Drop a PDF here/i);
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Ingest document/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('File upload rejected: storage quota exceeded.')).toBeDefined();
    });

    const alertBox = screen.getByRole('alert');
    expect(alertBox.getAttribute('aria-live')).toBe('assertive');
  });
});
