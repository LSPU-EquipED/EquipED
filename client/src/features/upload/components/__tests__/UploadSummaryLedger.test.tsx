// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { UploadSummaryLedger } from '../UploadSummaryLedger';
import type { DocumentUploadResponse } from '@/shared/types/documents';

const sourceTypeLabels = { slm: 'SLM' };

describe('UploadSummaryLedger', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders pre-upload summary ledger when uploadResult is null and no file is selected', () => {
    render(
      <UploadSummaryLedger
        uploadResult={null}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Intake Summary Ledger')).toBeDefined();
    expect(screen.getByText('Type')).toBeDefined();
    expect(screen.getByText('SLM')).toBeDefined();
    expect(screen.getByText('File')).toBeDefined();
    expect(screen.getByText('PENDING ATTACHMENT')).toBeDefined();
  });

  it('renders attached file name in pre-upload summary ledger', () => {
    const file = new File(['dummy'], 'IT201_Module1.pdf', { type: 'application/pdf' });
    render(
      <UploadSummaryLedger
        uploadResult={null}
        file={file}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('IT201_Module1.pdf')).toBeDefined();
  });

  it('renders PROCESSED result with success styling and metadata', () => {
    const result: DocumentUploadResponse = {
      documentId: 'doc-123',
      title: 'Operating Systems SLM',
      courseTitle: 'Operating Systems',
      courseCode: 'IT 301',
      lessonTitle: 'Process Scheduling',
      program: 'BSIT',
      academicYear: '1st Sem 2026-2027',
      sourceType: 'slm',
      processingStatus: 'PROCESSED',
      evaluationReadiness: 'READY',
    };

    render(
      <UploadSummaryLedger
        uploadResult={result}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Intake Process Result')).toBeDefined();
    expect(screen.getByText('Processed')).toBeDefined();
    expect(screen.getByText('Operating Systems SLM')).toBeDefined();
    expect(screen.getByText('BSIT')).toBeDefined();
    expect(screen.getByText('IT 301')).toBeDefined();
    expect(screen.getByText('1st Sem 2026-2027')).toBeDefined();
    expect(screen.getByText('Process Scheduling')).toBeDefined();
    expect(screen.queryByText('Failed')).toBeNull();
  });

  it('renders PENDING non-terminal status with Processing badge and no failure styling', () => {
    const result: DocumentUploadResponse = {
      documentId: 'doc-pending-1',
      title: 'Database Systems SLM',
      courseTitle: 'Database Systems',
      courseCode: 'IT 202',
      lessonTitle: null,
      program: 'BSIT',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'PENDING',
    };

    render(
      <UploadSummaryLedger
        uploadResult={result}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Processing')).toBeDefined();
    expect(screen.queryByText('Failed')).toBeNull();
    expect(screen.queryByText('Processed')).toBeNull();
    expect(
      screen.getByText(
        'Document intake is in progress. You do not need to upload again; you can track progress from My SLMs.',
      ),
    ).toBeDefined();
  });

  it('renders PROCESSING non-terminal status with Processing badge', () => {
    const result: DocumentUploadResponse = {
      documentId: 'doc-processing-1',
      title: 'Software Engineering SLM',
      courseTitle: 'Software Engineering',
      courseCode: 'IT 204',
      lessonTitle: null,
      program: 'BSIT',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'PROCESSING',
    };

    render(
      <UploadSummaryLedger
        uploadResult={result}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Processing')).toBeDefined();
    expect(screen.queryByText('Failed')).toBeNull();
    expect(screen.getByText('Software Engineering SLM')).toBeDefined();
    expect(
      screen.getByText(
        'Document intake is in progress. You do not need to upload again; you can track progress from My SLMs.',
      ),
    ).toBeDefined();
  });

  it('renders CLEANUP_PENDING non-terminal status with Processing badge', () => {
    const result: DocumentUploadResponse = {
      documentId: 'doc-cleanup-1',
      title: 'Networking Basics SLM',
      courseTitle: 'Networking Basics',
      courseCode: 'IT 101',
      lessonTitle: null,
      program: 'BSIT',
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'CLEANUP_PENDING',
    };

    render(
      <UploadSummaryLedger
        uploadResult={result}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Processing')).toBeDefined();
    expect(screen.queryByText('Failed')).toBeNull();
    expect(screen.getByText('Networking Basics SLM')).toBeDefined();
  });

  it('renders FAILED terminal status with Failed badge and error message', () => {
    const result: DocumentUploadResponse = {
      documentId: 'doc-failed-1',
      title: 'Corrupted Module SLM',
      courseTitle: null,
      courseCode: null,
      lessonTitle: null,
      program: null,
      academicYear: null,
      sourceType: 'slm',
      processingStatus: 'FAILED',
      errorMessage: 'PDF extraction failed because file stream is encrypted.',
    };

    render(
      <UploadSummaryLedger
        uploadResult={result}
        file={null}
        sourceTypeLabels={sourceTypeLabels}
        sourceType="slm"
      />,
    );

    expect(screen.getByText('Failed')).toBeDefined();
    expect(screen.queryByText('Processing')).toBeNull();
    expect(screen.queryByText('Processed')).toBeNull();
    expect(
      screen.getByText('PDF extraction failed because file stream is encrypted.'),
    ).toBeDefined();
  });
});
