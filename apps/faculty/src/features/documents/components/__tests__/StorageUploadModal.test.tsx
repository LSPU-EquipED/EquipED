// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import React from 'react';
import { documentsApi } from '@equiped/api-client';
import { StorageUploadModal } from '../StorageUploadModal';

vi.mock('@equiped/api-client', async () => {
  const actual = await vi.importActual<typeof import('@equiped/api-client')>('@equiped/api-client');
  return {
    ...actual,
    documentsApi: {
      uploadDocument: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('StorageUploadModal Component', () => {
  it('renders modal dialog when open with dropzone and form fields', () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    expect(screen.getByRole('dialog', { name: /Upload Course Learning Module/i })).toBeDefined();
    expect(screen.getByText(/Drag & drop your SLM PDF here/i)).toBeDefined();
    expect(screen.getByLabelText(/Module Title/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Academic Program/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Upload & Index/i })).toBeDefined();
  });

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <StorageUploadModal
        isOpen={false}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it('handles PDF file selection and auto-fills title from file name', async () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const file = new File(['%PDF-1.4 test content'], 'Operating-Systems-Module.pdf', {
      type: 'application/pdf',
    });

    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('Operating-Systems-Module.pdf')).toBeDefined();
      expect(screen.getByRole('button', { name: /Replace/i })).toBeDefined();
    });

    const titleInput = screen.getByLabelText(/Module Title/i) as HTMLInputElement;
    expect(titleInput.value).toBe('Operating-Systems-Module');
  });

  it('rejects non-PDF files with accessible error message', async () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const txtFile = new File(['plain text'], 'notes.txt', { type: 'text/plain' });
    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [txtFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText(/Only PDF documents \(\.pdf\) are supported/i)).toBeDefined();
    });
  });

  it('allows removing selected file', async () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const file = new File(['%PDF-1.4 test'], 'Compiler-Design.pdf', {
      type: 'application/pdf',
    });

    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('Compiler-Design.pdf')).toBeDefined();
    });

    const removeBtn = screen.getByRole('button', { name: /Remove selected file/i });
    fireEvent.click(removeBtn);

    expect(screen.queryByText('Compiler-Design.pdf')).toBeNull();
    expect(screen.getByText(/Drag & drop your SLM PDF here/i)).toBeDefined();
  });

  it('clears native file input value so re-selecting the exact same PDF works after removal', async () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const file = new File(['%PDF-1.4 test'], 'Compiler-Design.pdf', {
      type: 'application/pdf',
    });

    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('Compiler-Design.pdf')).toBeDefined();
    });

    // Remove the selected file
    const removeBtn = screen.getByRole('button', { name: /Remove selected file/i });
    fireEvent.click(removeBtn);

    expect(screen.queryByText('Compiler-Design.pdf')).toBeNull();
    expect(fileInput.value).toBe('');

    // Selecting the exact same file again must fire change and select the file
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('Compiler-Design.pdf')).toBeDefined();
    });
  });

  it('clears native file input value when a file is rejected so reselecting works', async () => {
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const invalidFile = new File(['plain text'], 'notes.txt', { type: 'text/plain' });
    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
      expect(fileInput.value).toBe('');
    });

    const validFile = new File(['%PDF-1.4 test'], 'notes.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [validFile] } });

    await waitFor(() => {
      expect(screen.getByText('notes.pdf')).toBeDefined();
    });
  });

  it('submits valid form data and invokes onSuccess callback', async () => {
    const handleSuccess = vi.fn();
    (documentsApi.uploadDocument as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      documentId: 'doc-new-123',
    });

    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={handleSuccess}
      />,
    );

    const file = new File(['%PDF-1.4 test content'], 'Algorithms-Unit-1.pdf', {
      type: 'application/pdf',
    });

    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Upload & Index/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(false);

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(documentsApi.uploadDocument).toHaveBeenCalledWith({
        file,
        sourceType: 'slm',
        title: 'Algorithms-Unit-1',
        program: 'BSCS',
      });
      expect(handleSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('handles upload errors and displays alert feedback', async () => {
    (documentsApi.uploadDocument as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network connectivity issue'),
    );

    render(
      <StorageUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );

    const file = new File(['%PDF-1.4 test content'], 'Web-Dev.pdf', {
      type: 'application/pdf',
    });

    const fileInput = document.getElementById('slm-upload-file-input') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    const submitBtn = screen.getByRole('button', { name: /Upload & Index/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
      expect(screen.getByText(/Network connectivity issue/i)).toBeDefined();
    });
  });

  it('triggers onClose when Cancel button is clicked', () => {
    const handleClose = vi.fn();
    render(
      <StorageUploadModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={vi.fn()}
      />,
    );

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
