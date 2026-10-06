import templateUrl from '../assets/pdf-templates/approval-sheet.pdf?url';
import type { MasterSynthesisDetailResponse } from '../types';
import { approvalSheetMetadata } from './approvalSheetMetadata';

export const APPROVAL_SHEET_LAYOUT = {
  width: 595.4,
  height: 841.7,
  valueColumn: [256.85, 540.3],
  tableRows: [
    ['materialType', 164.03, 188.53],
    ['courseTitle', 189.53, 214.03],
    ['authors', 215.03, 238.92],
    ['campus', 239.92, 263.82],
    ['college', 264.82, 291.82],
    ['academicYear', 292.82, 316.82],
    ['semester', 317.82, 341.93],
  ],
  reviewerLines: {
    sme: [72, 396.55, 236.508],
    coordinator: [324.05, 396.55, 519.638],
    gad: [72, 438.75, 236.508],
    itso: [324.05, 438.75, 519.638],
  },
  signatoryLines: {
    dean: [72, 480.95, 236.508],
    chairperson: [324.05, 480.95, 519.638],
    director: [143.02, 565.35, 316.582],
    vicePresident: [143.02, 621.67, 316.582],
  },
} as const;

/** Fill the supplied institutional page without redrawing it or appending a report. */
export async function createApprovalSheetPdf(
  data: MasterSynthesisDetailResponse,
  templateBytes: Uint8Array,
): Promise<Uint8Array> {
  const [{ jsPDF }, { PDFDocument, StandardFonts }] = await Promise.all([import('jspdf'), import('pdf-lib')]);
  const source = await PDFDocument.load(templateBytes);
  const layout = APPROVAL_SHEET_LAYOUT;
  if (source.getPageCount() !== 1) throw new Error('Unexpected approval-sheet page count.');
  const page = source.getPage(0);
  if (Math.abs(page.getWidth() - layout.width) > 0.1 || Math.abs(page.getHeight() - layout.height) > 0.1) {
    throw new Error('Unexpected approval-sheet dimensions.');
  }
  const fields = approvalSheetMetadata(data);
  // Use the actual standard face's advance widths for centered names; jsPDF's
  // rounded width table can shift longer, punctuated names off their rules.
  const times = await source.embedFont(StandardFonts.TimesRoman);
  const overlay = new jsPDF({ unit: 'pt', format: [layout.width, layout.height] });
  overlay.setFont('times', 'normal');
  overlay.setFontSize(12);
  overlay.setTextColor(0, 0, 0);
  const clean = (value: string) => value.replace(/\s+/g, ' ').trim();
  const [columnLeft, columnRight] = layout.valueColumn;
  for (const [key, top, bottom] of layout.tableRows) {
    const value = clean(fields[key]);
    if (!value) continue;
    const lines: string[] = overlay.splitTextToSize(value, columnRight - columnLeft - 12);
    if (lines.length > 2) throw new Error(`${key} is too long for the approval sheet.`);
    const lineHeight = 11.5;
    const baseline = (top + bottom) / 2 + 4 - (lines.length - 1) * lineHeight / 2;
    lines.forEach((line, index) => overlay.text(line, columnLeft + 6, baseline + index * lineHeight));
  }
  const printedName = (value: string, [left, baseline, right]: readonly [number, number, number], inset: number) => {
    const name = clean(value);
    if (!name) return;
    // A printed name must remain complete, never silently shorten a signatory.
    const width = times.widthOfTextAtSize(name, 12);
    if (width > right - left - inset * 2) {
      throw new Error('An evaluator or signatory name is too long for the approval sheet.');
    }
    overlay.text(name, (left + right - width) / 2, baseline - 2);
  };
  for (const [agent, line] of Object.entries(layout.reviewerLines)) {
    printedName(fields.reviewers[agent], line, 4);
  }
  for (const [role, line] of Object.entries(layout.signatoryLines)) {
    printedName(fields.signatories[role as keyof typeof fields.signatories], line, 2);
  }
  // Only printed names are prefilled. Signatures and approval dates stay blank:
  // automated completion does not establish institutional approval.
  const [filledPage] = await source.embedPdf(overlay.output('arraybuffer'), [0]);
  page.drawPage(filledPage, { x: 0, y: 0, width: layout.width, height: layout.height });
  source.setTitle('LSPU-CID-SF-006 - Approval sheet');
  source.setCreator('EquipED');
  return source.save();
}

export async function downloadApprovalSheetPdf(data: MasterSynthesisDetailResponse): Promise<void> {
  const response = await fetch(templateUrl);
  if (!response.ok) throw new Error('The approval-sheet template could not be loaded.');
  const bytes = await createApprovalSheetPdf(data, new Uint8Array(await response.arrayBuffer()));
  const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'LSPU-CID-SF-006-approval-sheet.pdf';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
