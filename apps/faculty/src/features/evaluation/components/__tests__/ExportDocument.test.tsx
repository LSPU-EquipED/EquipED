// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SpecialistExportDownloadButton } from '../ExportDocument';
import { loadSpecialistPdfMetadata } from '../../utils/specialistPdfMetadata';
import { downloadSpecialistPdf } from '../../utils/specialistPdf';
import type { ExportDomainData } from '../../types';

vi.mock('../../utils/specialistPdfMetadata', () => ({ loadSpecialistPdfMetadata: vi.fn() }));
vi.mock('../../utils/specialistPdf', () => ({ downloadSpecialistPdf: vi.fn() }));

const data: ExportDomainData = { agentId: 'sme', criteria: [], subtotal: 3, max_score: 4, status: 'OK' };

describe('specialist PDF download', () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('downloads the form with resolved faculty and module metadata', async () => {
    const resolved = { ...data, facultyName: 'José Santos', courseTitle: 'HCI', college: 'CCS', academicYear: '2026-2027' };
    vi.mocked(loadSpecialistPdfMetadata).mockResolvedValue(resolved);
    render(<SpecialistExportDownloadButton domainData={data} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF - SME Scorecard' }));
    await waitFor(() => expect(downloadSpecialistPdf).toHaveBeenCalledWith(resolved));
    expect(loadSpecialistPdfMetadata).toHaveBeenCalledWith(data);
  });

  it('reports unavailable module metadata without downloading an incomplete substitute', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.mocked(loadSpecialistPdfMetadata).mockRejectedValue(new Error('Document not found'));
    render(<SpecialistExportDownloadButton domainData={data} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF - SME Scorecard' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('PDF export failed'));
    expect(downloadSpecialistPdf).not.toHaveBeenCalled();
  });
});
