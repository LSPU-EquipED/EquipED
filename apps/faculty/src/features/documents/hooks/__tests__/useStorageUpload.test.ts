// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStorageUpload } from '../useStorageUpload';
import { documentsApi } from '@equiped/api-client';

vi.mock('@equiped/api-client', async () => {
  const actual = await vi.importActual<typeof import('@equiped/api-client')>('@equiped/api-client');
  return {
    ...actual,
    documentsApi: {
      uploadDocument: vi.fn(),
    },
  };
});

describe('useStorageUpload Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with default state', () => {
    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess: vi.fn() }));

    expect(result.current.file).toBeNull();
    expect(result.current.title).toBe('');
    expect(result.current.program).toBe('BSCS');
    expect(result.current.isDragging).toBe(false);
    expect(result.current.isUploading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('validates and accepts a valid PDF file and autofills title', () => {
    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess: vi.fn() }));
    const pdfFile = new File(['dummy pdf content'], 'Intro_Algorithms.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.handleFileChange(pdfFile);
    });

    expect(result.current.file).toBe(pdfFile);
    expect(result.current.title).toBe('Intro_Algorithms');
    expect(result.current.error).toBeNull();
  });

  it('rejects non-PDF files', () => {
    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess: vi.fn() }));
    const docFile = new File(['text content'], 'notes.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });

    act(() => {
      result.current.handleFileChange(docFile);
    });

    expect(result.current.file).toBeNull();
    expect(result.current.error).toBe('Only PDF documents (.pdf) are supported for course SLM storage.');
  });

  it('rejects files larger than 50MB', () => {
    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess: vi.fn() }));
    const largeFile = new File(['dummy'], 'huge.pdf', { type: 'application/pdf' });
    Object.defineProperty(largeFile, 'size', { value: 50 * 1024 * 1024 + 1 });

    act(() => {
      result.current.handleFileChange(largeFile);
    });

    expect(result.current.file).toBeNull();
    expect(result.current.error).toBe('The selected PDF exceeds the 50 MB limit. Please select a smaller file.');
  });

  it('clears file when handleFileChange is called with null', () => {
    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess: vi.fn() }));
    const pdfFile = new File(['dummy'], 'module.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.handleFileChange(pdfFile);
    });
    expect(result.current.file).toBe(pdfFile);

    act(() => {
      result.current.handleFileChange(null);
    });
    expect(result.current.file).toBeNull();
  });

  it('resets state when isOpen changes to false', () => {
    let isOpen = true;
    const { result, rerender } = renderHook(() => useStorageUpload({ isOpen, onSuccess: vi.fn() }));
    const pdfFile = new File(['dummy'], 'module.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.handleFileChange(pdfFile);
      result.current.setProgram('BSInfoTech');
      result.current.setIsDragging(true);
    });

    expect(result.current.file).toBe(pdfFile);
    expect(result.current.program).toBe('BSInfoTech');

    isOpen = false;
    rerender();

    expect(result.current.file).toBeNull();
    expect(result.current.title).toBe('');
    expect(result.current.program).toBe('BSCS');
    expect(result.current.isDragging).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handles successful upload', async () => {
    const onSuccess = vi.fn();
    vi.mocked(documentsApi.uploadDocument).mockResolvedValue({
      documentId: 'doc-new',
      title: 'Module 1',
      program: 'BSCS',
      courseTitle: '',
      lessonTitle: '',
      sourceType: 'slm',
      academicYear: '2025-2026',
      courseCode: '',
      processingStatus: 'PENDING',
    });

    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess }));
    const pdfFile = new File(['dummy'], 'module.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.handleFileChange(pdfFile);
    });

    const mockEvent = { preventDefault: vi.fn() } as unknown as React.FormEvent;
    await act(async () => {
      await result.current.handleSubmit(mockEvent);
    });

    expect(documentsApi.uploadDocument).toHaveBeenCalledWith({
      file: pdfFile,
      sourceType: 'slm',
      title: 'module',
      program: 'BSCS',
    });
    expect(result.current.isUploading).toBe(false);
    expect(onSuccess).toHaveBeenCalled();
  });

  it('handles upload failure with error message', async () => {
    const onSuccess = vi.fn();
    vi.mocked(documentsApi.uploadDocument).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useStorageUpload({ isOpen: true, onSuccess }));
    const pdfFile = new File(['dummy'], 'module.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.handleFileChange(pdfFile);
    });

    const mockEvent = { preventDefault: vi.fn() } as unknown as React.FormEvent;
    await act(async () => {
      await result.current.handleSubmit(mockEvent);
    });

    expect(result.current.isUploading).toBe(false);
    expect(result.current.error).toBe('Network error');
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
