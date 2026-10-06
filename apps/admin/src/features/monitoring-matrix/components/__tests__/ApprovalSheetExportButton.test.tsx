// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApprovalSheetExportButton } from '../ApprovalSheetExportButton';
import { downloadApprovalSheetPdf } from '../../utils/approvalSheetPdf';
import { approvalSheetData } from '../../utils/__tests__/approvalSheet.fixture';

vi.mock('../../utils/approvalSheetPdf', () => ({ downloadApprovalSheetPdf: vi.fn() }));

describe('approval-sheet download', () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(cleanup);

  it('keeps export disabled while generating the selected record', async () => {
    let finish!: () => void;
    vi.mocked(downloadApprovalSheetPdf).mockImplementation(() => new Promise<void>((resolve) => { finish = resolve; }));
    const data = approvalSheetData();
    render(<ApprovalSheetExportButton data={data} />);
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
    expect(screen.getByRole('button', { name: 'Creating approval sheet PDF' }).hasAttribute('disabled')).toBe(true);
    expect(downloadApprovalSheetPdf).toHaveBeenCalledTimes(1);
    expect(downloadApprovalSheetPdf).toHaveBeenCalledWith(data);
    finish();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export PDF' }).hasAttribute('disabled')).toBe(false));
  });

  it('shows a generation error and allows a successful retry', async () => {
    vi.mocked(downloadApprovalSheetPdf).mockRejectedValueOnce(new Error('Template unavailable')).mockResolvedValueOnce(undefined);
    render(<ApprovalSheetExportButton data={approvalSheetData()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Template unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
    await waitFor(() => expect(downloadApprovalSheetPdf).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
