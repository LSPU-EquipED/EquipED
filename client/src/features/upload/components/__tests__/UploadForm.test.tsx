// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UploadForm } from '../UploadForm';
import type { DocumentUploadResponse } from '@/shared/types/documents';

const mockNavigate = vi.fn();
const mockInvalidateQueries = vi.fn();
const mockUploadDocument = vi.fn();
const mockResetUpload = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
  }),
}));

const mockUser = { displayName: 'Dr. Santos', role: 'faculty' };

let mockHookState = {
  isLoading: false,
  errorMessage: null as string | null,
};

vi.mock('@/features/upload/hooks/useUploadDocument', () => ({
  useUploadDocument: () => ({
    uploadDocument: mockUploadDocument,
    isLoading: mockHookState.isLoading,
    errorMessage: mockHookState.errorMessage,
    setData: mockResetUpload,
  }),
}));

describe('UploadForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHookState = {
      isLoading: false,
      errorMessage: null,
    };
  });

  afterEach(() => {
    cleanup();
  });

  it('renders intake fields, dropzone, and pre-upload ledger with disabled submit when empty', () => {
    render(<UploadForm user={mockUser} />);

    expect(screen.getByText('LSPU SCC Faculty Document Intake')).toBeDefined();
    expect(screen.getByText('Welcome back, Dr..')).toBeDefined();
    expect(screen.getByText('Intake Summary Ledger')).toBeDefined();
    expect(screen.getByText('Missing details')).toBeDefined();

    const submitBtn = screen.getByRole('button', { name: /upload document/i });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('rejects non-PDF files selected via file picker and announces validation error accessibly', async () => {
    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const docxFile = new File(['dummy content'], 'module_notes.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });

    fireEvent.change(fileInput, { target: { files: [docxFile] } });

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain('Only PDF documents are supported for SLM upload');
    expect(alert.getAttribute('aria-live')).toBe('polite');

    expect(screen.getByText('PENDING ATTACHMENT')).toBeDefined();

    const submitBtn = screen.getByRole('button', { name: /upload document/i });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('rejects non-PDF files dropped via drag and drop and announces validation error', () => {
    render(<UploadForm user={mockUser} />);

    const label = document.querySelector('label[for="pdf-file"]') as HTMLLabelElement;
    const pngFile = new File(['image data'], 'diagram.png', { type: 'image/png' });

    fireEvent.drop(label, {
      dataTransfer: {
        files: [pngFile],
      },
    });

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain('Only PDF documents are supported for SLM upload');
    expect(screen.getByText('PENDING ATTACHMENT')).toBeDefined();
  });

  it('accepts valid PDF file, clears validation error, and auto-populates title', () => {
    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf binary data'], 'Data_Structures_Module.pdf', {
      type: 'application/pdf',
    });

    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getAllByText('Data_Structures_Module.pdf').length).toBe(2);

    const titleInput = screen.getByLabelText(/document title/i) as HTMLInputElement;
    expect(titleInput.value).toBe('Data_Structures_Module');

    expect(screen.getByText('Ready')).toBeDefined();
    const submitBtn = screen.getByRole('button', { name: /upload document/i });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(false);
  });

  it('preserves PROCESSED auto-navigation to evaluation route exactly', async () => {
    const processedResponse: DocumentUploadResponse = {
      documentId: 'doc-ready-99',
      title: 'Operating Systems',
      courseTitle: 'IT 301',
      courseCode: 'IT301',
      lessonTitle: 'Memory Management',
      program: 'BSIT',
      academicYear: '2026-2027',
      sourceType: 'slm',
      processingStatus: 'PROCESSED',
    };

    mockUploadDocument.mockResolvedValueOnce(processedResponse);

    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf content'], 'Operating_Systems.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    const submitBtn = screen.getByRole('button', { name: /upload document/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockUploadDocument).toHaveBeenCalledTimes(1);
    });

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['documents'] });
    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/documents/$documentId/evaluation',
      params: { documentId: 'doc-ready-99' },
    });
  });

  it('handles PENDING non-terminal status with Processing messaging, View in My SLMs CTA, and no retry CTA', async () => {
    const pendingResponse: DocumentUploadResponse = {
      documentId: 'doc-pending-88',
      title: 'Web Development SLM',
      courseTitle: 'IT 205',
      courseCode: 'IT205',
      lessonTitle: null,
      program: 'BSIT',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'PENDING',
    };

    mockUploadDocument.mockResolvedValueOnce(pendingResponse);

    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf content'], 'Web_Development.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    const submitBtn = screen.getByRole('button', { name: /upload document/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    });

    // Does NOT auto-navigate to evaluation
    expect(mockNavigate).not.toHaveBeenCalled();

    // Displays truthful non-terminal messaging
    expect(
      screen.getByText('Your document was uploaded and is currently processing in the background.'),
    ).toBeDefined();
    expect(
      screen.getByText(
        'Processing continues in the background. Check My SLMs to start evaluation once ready.',
      ),
    ).toBeDefined();

    // Renders View in My SLMs action and NO retry CTA
    const viewBtn = screen.getByRole('button', { name: /view in my slms/i });
    expect(viewBtn).toBeDefined();
    expect(screen.queryByRole('button', { name: /try uploading again/i })).toBeNull();

    // Clicking View in My SLMs navigates to /documents with highlight
    fireEvent.click(viewBtn);
    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/documents',
      search: { highlight: 'doc-pending-88' },
    });
  });

  it('handles PROCESSING non-terminal status with Processing messaging and View in My SLMs CTA', async () => {
    const processingResponse: DocumentUploadResponse = {
      documentId: 'doc-proc-77',
      title: 'AI Fundamentals',
      courseTitle: 'CS 401',
      courseCode: 'CS401',
      lessonTitle: null,
      program: 'BSCS',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'PROCESSING',
    };

    mockUploadDocument.mockResolvedValueOnce(processingResponse);

    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf content'], 'AI_Fundamentals.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    fireEvent.click(screen.getByRole('button', { name: /upload document/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    });

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /view in my slms/i })).toBeDefined();
    expect(screen.queryByRole('button', { name: /try uploading again/i })).toBeNull();
  });

  it('handles CLEANUP_PENDING non-terminal status with Processing messaging and View in My SLMs CTA', async () => {
    const cleanupResponse: DocumentUploadResponse = {
      documentId: 'doc-clean-66',
      title: 'Cloud Computing',
      courseTitle: 'IT 402',
      courseCode: 'IT402',
      lessonTitle: null,
      program: 'BSIT',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'CLEANUP_PENDING',
    };

    mockUploadDocument.mockResolvedValueOnce(cleanupResponse);

    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf content'], 'Cloud_Computing.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    fireEvent.click(screen.getByRole('button', { name: /upload document/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    });

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /view in my slms/i })).toBeDefined();
    expect(screen.queryByRole('button', { name: /try uploading again/i })).toBeNull();
  });

  it('handles FAILED terminal status with Failed messaging, error display, and retry guidance CTA', async () => {
    const failedResponse: DocumentUploadResponse = {
      documentId: 'doc-fail-55',
      title: 'Corrupted File SLM',
      courseTitle: null,
      courseCode: null,
      lessonTitle: null,
      program: null,
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'FAILED',
      errorMessage: 'Local OCR parsing failed on corrupted pages.',
    };

    mockUploadDocument.mockResolvedValueOnce(failedResponse);

    render(<UploadForm user={mockUser} />);

    const fileInput = document.getElementById('pdf-file') as HTMLInputElement;
    const pdfFile = new File(['pdf content'], 'Corrupted_File.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    fireEvent.click(screen.getByRole('button', { name: /upload document/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    });

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(
      screen.getByText('Upload completed, but document processing failed.'),
    ).toBeDefined();
    expect(
      screen.getByText('Local OCR parsing failed on corrupted pages.'),
    ).toBeDefined();
    expect(
      screen.getByText(
        'You can try uploading the file again or contact support if the issue persists.',
      ),
    ).toBeDefined();

    // Renders Try Uploading Again retry button and NO View in My SLMs
    const retryBtn = screen.getByRole('button', { name: /try uploading again/i });
    expect(retryBtn).toBeDefined();
    expect(screen.queryByRole('button', { name: /view in my slms/i })).toBeNull();

    // Clicking retry resets the form
    fireEvent.click(retryBtn);
    expect(screen.getByText('Review the upload details, then upload the document to begin.')).toBeDefined();
    expect(screen.getByText('PENDING ATTACHMENT')).toBeDefined();
  });
});
