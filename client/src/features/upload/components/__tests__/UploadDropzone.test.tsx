// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { UploadDropzone } from '../UploadDropzone';

describe('UploadDropzone', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders default dropzone prompt and Browse Files button when no file is selected', () => {
    const fileInputRef = createRef<HTMLInputElement>();
    render(
      <UploadDropzone
        file={null}
        isDragging={false}
        handleDragOver={vi.fn()}
        handleDragLeave={vi.fn()}
        handleDrop={vi.fn()}
        handleFileChange={vi.fn()}
        handleReset={vi.fn()}
        fileInputRef={fileInputRef}
      />,
    );

    expect(screen.getByText('Select or drag the SLM PDF file')).toBeDefined();
    expect(screen.getByText('PDF ONLY • SYSTEM INTAKE')).toBeDefined();
    expect(screen.getByText('Browse Files')).toBeDefined();
    expect(screen.queryByText('Remove File')).toBeNull();
  });

  it('renders attached file name and Remove File button when a file is provided', () => {
    const file = new File(['dummy content'], 'CS101_Module.pdf', { type: 'application/pdf' });
    const fileInputRef = createRef<HTMLInputElement>();
    const handleReset = vi.fn();

    render(
      <UploadDropzone
        file={file}
        isDragging={false}
        handleDragOver={vi.fn()}
        handleDragLeave={vi.fn()}
        handleDrop={vi.fn()}
        handleFileChange={vi.fn()}
        handleReset={handleReset}
        fileInputRef={fileInputRef}
      />,
    );

    expect(screen.getByText('CS101_Module.pdf')).toBeDefined();
    expect(screen.getByText('Remove File')).toBeDefined();

    fireEvent.click(screen.getByText('Remove File'));
    expect(handleReset).toHaveBeenCalledTimes(1);
  });

  it('renders accessible validation error alert when validationError is provided', () => {
    const fileInputRef = createRef<HTMLInputElement>();
    render(
      <UploadDropzone
        file={null}
        isDragging={false}
        validationError="Only PDF documents are supported for SLM upload. Please select a valid .pdf file."
        handleDragOver={vi.fn()}
        handleDragLeave={vi.fn()}
        handleDrop={vi.fn()}
        handleFileChange={vi.fn()}
        handleReset={vi.fn()}
        fileInputRef={fileInputRef}
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.getAttribute('aria-live')).toBe('polite');
    expect(alert.textContent).toContain(
      'Only PDF documents are supported for SLM upload. Please select a valid .pdf file.',
    );

    const input = document.getElementById('pdf-file') as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('pdf-file-error');
  });
});
