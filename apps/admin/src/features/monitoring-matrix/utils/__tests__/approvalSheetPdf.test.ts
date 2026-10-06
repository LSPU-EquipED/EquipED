import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { PDFDict, PDFDocument, PDFName, PDFRawStream, StandardFonts, decodePDFRawStream } from 'pdf-lib';
import { APPROVAL_SHEET_LAYOUT, createApprovalSheetPdf } from '../approvalSheetPdf';
import { approvalSheetMetadata } from '../approvalSheetMetadata';
import { approvalSheetData } from './approvalSheet.fixture';

const templatePath = resolve(__dirname, '../../assets/pdf-templates/approval-sheet.pdf');
async function exportPdf(data = approvalSheetData()) {
  const bytes = await createApprovalSheetPdf(data, await readFile(templatePath));
  const pdf = await PDFDocument.load(bytes);
  const objects = pdf.getPage(0).node.Resources()!.lookup(PDFName.of('XObject'), PDFDict);
  const overlay = objects.values().map((value) => pdf.context.lookup(value))
    .find((value): value is PDFRawStream => value instanceof PDFRawStream
      && value.dict.get(PDFName.of('Subtype')) === PDFName.of('Form'))!;
  return { pdf, overlay, fields: new TextDecoder().decode(decodePDFRawStream(overlay).decode()) };
}

describe('institutional approval-sheet export', () => {
  it('preserves the original single-page template and fills only its requested information', async () => {
    const template = await readFile(templatePath);
    expect(createHash('sha256').update(template).digest('hex')).toBe('ff5398cee13899e0593782d42a0c86e6173837532923bcc7ac4f8d0186428ed9');
    const { pdf, fields } = await exportPdf();
    expect(pdf.getPageCount()).toBe(1);
    expect(pdf.getPage(0).getWidth()).toBe(APPROVAL_SHEET_LAYOUT.width);
    expect(pdf.getPage(0).getHeight()).toBe(APPROVAL_SHEET_LAYOUT.height);
    for (const value of ['Self-paced Learning Module', 'Human-computer interaction',
      'Santa Cruz Campus', 'College of Computer Studies', '2026-2027',
      'ANA REYES', 'JOSE CRUZ', 'MARIA GARCIA', 'PEDRO SANTOS',
      'DR. MIA V. VILLARICA', 'MAIDA O. SARMIENTO',
      'DR. ELAINE ROSE G. NACHON', 'ATTY. RUSHID JAY S. SANCON']) {
      expect(fields).toContain(value);
    }
    expect(fields).not.toMatch(/private|advisory|\(79\) Tj|Satisfactory|Module title|Oct 7|2026-10-07|Page 1/);
    expect(fields).not.toContain('Maria Santos');
    // The two human approval dates stay blank, even though printed names are known.
    const positions = [...fields.matchAll(/([\d.]+) ([\d.]+) Td\n\([^\n]+\) Tj/g)]
      .map((match) => ({ x: Number(match[1]), baseline: APPROVAL_SHEET_LAYOUT.height - Number(match[2]) }));
    expect(positions.filter(({ baseline, x }) => baseline > 550 && x >= 359)).toHaveLength(0);
    const [, authorTop, authorBottom] = APPROVAL_SHEET_LAYOUT.tableRows.find(([key]) => key === 'authors')!;
    expect(positions.filter(({ baseline }) => baseline > authorTop && baseline < authorBottom)).toHaveLength(0);
  });

  it('uses 12 pt Times and centers uppercase evaluator names on their own rules', async () => {
    const { pdf, overlay, fields } = await exportPdf();
    const fonts = overlay.dict.lookup(PDFName.of('Resources'), PDFDict).lookup(PDFName.of('Font'), PDFDict);
    const selections = [...fields.matchAll(/\/([^\s]+) ([\d.]+) Tf/g)];
    expect(selections.length).toBeGreaterThan(0);
    for (const [, key, size] of selections) {
      expect(Number(size)).toBe(12);
      expect(fonts.lookup(PDFName.of(key), PDFDict).get(PDFName.of('BaseFont'))?.toString()).toBe('/Times-Roman');
    }
    const face = await pdf.embedFont(StandardFonts.TimesRoman);
    const names = approvalSheetMetadata(approvalSheetData()).reviewers;
    for (const [agent, [left, baseline, right]] of Object.entries(APPROVAL_SHEET_LAYOUT.reviewerLines)) {
      const name = names[agent];
      const position = fields.match(new RegExp(`([\\d.]+) ([\\d.]+) Td\\n\\(${name}\\) Tj`))!;
      expect(Number(position[1]) + face.widthOfTextAtSize(name, 12) / 2).toBeCloseTo((left + right) / 2, 0);
      expect(APPROVAL_SHEET_LAYOUT.height - Number(position[2])).toBeCloseTo(baseline - 2, 2);
    }
    const signatories = approvalSheetMetadata(approvalSheetData()).signatories;
    for (const [role, [left, baseline, right]] of Object.entries(APPROVAL_SHEET_LAYOUT.signatoryLines)) {
      const name = signatories[role as keyof typeof signatories];
      const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const position = fields.match(new RegExp(`([\\d.]+) ([\\d.]+) Td\\n\\(${escaped}\\) Tj`))!;
      const width = face.widthOfTextAtSize(name, 12);
      expect(width).toBeLessThan(right - left - 4);
      expect(Number(position[1]) + width / 2).toBeCloseTo((left + right) / 2, 0);
      expect(APPROVAL_SHEET_LAYOUT.height - Number(position[2])).toBeCloseTo(baseline - 2, 2);
    }
  });

  it('leaves unknown authors, missing metadata and incomplete/failed evaluator names blank', async () => {
    const data = approvalSheetData();
    data.author.name = 'Unknown Author';
    data.course_title = null;
    data.academic_year = null;
    data.program = 'Unknown';
    data.pillars.sme.evaluator!.name = 'Unknown Evaluator';
    data.pillars.gad.status = 'FAILED';
    data.pillars.itso.subtotal = null;
    const { fields } = await exportPdf(data);
    expect(fields).toContain('JOSE CRUZ');
    expect(fields).not.toMatch(/Unknown|UNKNOWN|MARIA GARCIA|PEDRO SANTOS|College|2026-2027|Module title/);
    expect(fields).not.toContain('DR. MIA V. VILLARICA');
  });

  it.each(['BSCS', 'BSIT'])('uses the supplied CCS dean for %s', (program) => {
    const data = approvalSheetData();
    data.program = program;
    expect(approvalSheetMetadata(data).signatories.dean).toBe('DR. MIA V. VILLARICA');
  });

  it('wraps a long course title inside its table row without shortening it', async () => {
    const data = approvalSheetData();
    data.course_title = 'Introduction to Human-Computer Interaction and Interface Design';
    const { fields } = await exportPdf(data);
    const text = [...fields.matchAll(/\(([^\n]+)\) Tj/g)].map((match) => match[1]).join(' ');
    expect(text).toContain(data.course_title);
    expect(fields).not.toContain('...');
  });

  it('rejects overflowing fields instead of silently truncating a printed name', async () => {
    const data = approvalSheetData();
    data.pillars.sme.evaluator!.name = 'A very long institutional evaluator name that cannot fit';
    await expect(exportPdf(data)).rejects.toThrow('name is too long');
    data.pillars.sme.evaluator = null;
    data.course_title = 'An extremely long course title '.repeat(20);
    await expect(exportPdf(data)).rejects.toThrow('courseTitle is too long');
  });
});
