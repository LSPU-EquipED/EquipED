import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { PDFDocument, PDFDict, PDFName, PDFRawStream, StandardFonts, decodePDFRawStream } from 'pdf-lib';
import type { ExportAgentId, ExportDomainData } from '../../types';
import { createSpecialistPdf } from '../specialistPdf';
import { matchTemplateCriteria, SPECIALIST_PDF_TEMPLATES } from '../specialistPdfTemplates';

const templateDirectory = resolve(__dirname, '../../assets/pdf-templates');
const sourceDirectory = resolve(__dirname, '../../../../../../server/data/rubrics/source');
const agents: ExportAgentId[] = ['sme', 'coordinator', 'gad', 'itso'];

function result(agentId: ExportAgentId): ExportDomainData {
  return {
    agentId, documentTitle: 'Human-computer interaction module', program: 'BSCS',
    courseTitle: 'Human-computer interaction', courseCode: 'CS101', academicYear: '2026-2027',
    semester: '1st', facultyName: 'José Santos', college: 'CCS', reviewer: 'Maria Cruz', evaluatedAt: '2026-10-05',
    subtotal: 3, max_score: 4, status: 'OK', evaluationStatus: 'COMPLETED',
    adjectival_rating: 'Satisfactory', version: 3, form_snapshot_id: 'saved-form',
    summary: 'Advisory review for institutional verification.',
    criteria: SPECIALIST_PDF_TEMPLATES[agentId].rows.map((row) => ({
      criterion_id: row.criterionCode, criterion_text: row.title,
      description: row.text, score: 3, justification: 'Supported by the module content.',
    })),
  };
}

// Read just the filled fields (the embedded overlay), independently of the
// untouched source form's printed numbers and instructions.
function filledFields(pdf: PDFDocument): string {
  const objects = pdf.getPage(0).node.Resources()!.lookup(PDFName.of('XObject'), PDFDict);
  return objects.values().map((value) => {
    const object = pdf.context.lookup(value);
    return object instanceof PDFRawStream && object.dict.get(PDFName.of('Subtype')) === PDFName.of('Form')
      ? new TextDecoder().decode(decodePDFRawStream(object).decode()) : '';
  }).join('\n');
}

async function exportPdf(data: ExportDomainData): Promise<PDFDocument> {
  return PDFDocument.load(await createSpecialistPdf(data, {
    templateBytes: await readFile(resolve(templateDirectory, `${data.agentId}.pdf`)),
  }));
}

describe('institutional specialist PDFs', () => {
  it.each(agents)('fills only the original %s form without additional pages or text', async (agent) => {
    const template = SPECIALIST_PDF_TEMPLATES[agent];
    const bytes = await readFile(resolve(templateDirectory, `${agent}.pdf`));
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(template.sha256);
    const sourceFiles = {
      sme: 'LSPU-CID-SF-002-CRITERIA FOR SME.pdf',
      coordinator: 'LSPU-CID-SF-003-CRITERIA FOR PROG COOR.pdf',
      gad: 'LSPU-CID-SF-004-CRITERIA FOR GAD.pdf',
      itso: 'LSPU-CID-SF-005-CRITERIA FOR ITSO.pdf',
    };
    expect(bytes.equals(await readFile(resolve(sourceDirectory, agent, sourceFiles[agent])))).toBe(true);
    const pdf = await PDFDocument.load(await createSpecialistPdf(result(agent), { templateBytes: bytes }));
    expect(pdf.getPageCount()).toBe(1);
    expect(pdf.getPage(0).getWidth()).toBe(template.width);
    expect(pdf.getPage(0).getHeight()).toBe(template.height);
    expect(pdf.getTitle()).toContain(template.code);
    const fields = filledFields(pdf);
    expect(fields).toContain('(15) Tj');
    expect(fields).toContain('(3) Tj');
    expect(fields).toContain('(Satisfactory) Tj');
    expect(fields).toContain('(Oct 5, 2026) Tj');
    expect(fields).toContain('(MARIA CRUZ) Tj');
    expect(fields).not.toContain('(Maria Cruz) Tj');
    expect(fields).not.toMatch(/Saved rubric|EquipED advisory copy|attached|Page 1/);
    // Resolve the actual face selected by text operators, rather than checking
    // unused standard fonts that jsPDF also includes in its resource dictionary.
    const objects = pdf.getPage(0).node.Resources()!.lookup(PDFName.of('XObject'), PDFDict);
    const overlay = objects.values().map((value) => pdf.context.lookup(value))
      .find((object): object is PDFRawStream => object instanceof PDFRawStream
        && object.dict.get(PDFName.of('Subtype')) === PDFName.of('Form'))!;
    const fonts = overlay.dict.lookup(PDFName.of('Resources'), PDFDict).lookup(PDFName.of('Font'), PDFDict);
    const selections = [...fields.matchAll(/\/([^\s]+) ([\d.]+) Tf/g)];
    expect(selections.length).toBeGreaterThan(0);
    for (const [, key, size] of selections) {
      expect(Number(size)).toBe(12);
      expect(fonts.lookup(PDFName.of(key), PDFDict).get(PDFName.of('BaseFont'))?.toString()).toBe('/Times-Roman');
    }
    const datePosition = fields.match(/([\d.]+) ([\d.]+) Td\n\(Oct 5, 2026\) Tj/)!;
    const face = await pdf.embedFont(StandardFonts.TimesRoman);
    const dateWidth = face.widthOfTextAtSize('Oct 5, 2026', 12);
    const [left, baseline, right] = template.evaluatedDateLine;
    expect(Number(datePosition[1]) + dateWidth / 2).toBeCloseTo((left + right) / 2, 0);
    expect(template.height - Number(datePosition[2])).toBeCloseTo(baseline - 2, 2);
    const namePosition = fields.match(/([\d.]+) ([\d.]+) Td\n\(MARIA CRUZ\) Tj/)!;
    const nameWidth = face.widthOfTextAtSize('MARIA CRUZ', 12);
    const [nameLeft, nameBaseline, nameRight] = template.signatureNameLine;
    expect(Number(namePosition[1]) + nameWidth / 2).toBeCloseTo((nameLeft + nameRight) / 2, 0);
    expect(template.height - Number(namePosition[2])).toBeCloseTo(nameBaseline - 2, 2);
  });

  it('leaves the printed name blank when no evaluator is known, without using the module author', async () => {
    const fields = filledFields(await exportPdf({ ...result('sme'), reviewer: null, facultyName: 'Module Author' }));
    expect(fields).toContain('(Module Author) Tj');
    expect(fields).not.toContain('(MODULE AUTHOR) Tj');
    expect(fields).not.toContain('(MARIA CRUZ) Tj');
  });

  it('matches wording independently of row order and typographic punctuation', () => {
    const data = result('sme');
    data.criteria = [...data.criteria].reverse().map((row) => ({
      ...row, description: row.description?.replace(/’/g, "'"),
    }));
    const mapping = matchTemplateCriteria('sme', data.criteria);
    expect(mapping.complete).toBe(true);
    expect(mapping.matches[0]?.criterion_id).toBe('OP-01');
  });

  it.each(agents)('fills title-only legacy %s scores using canonical codes and titles', (agent) => {
    const data = result(agent);
    data.criteria = [...data.criteria].reverse().map((row) => ({ ...row, description: null }));
    expect(matchTemplateCriteria(agent, data.criteria).complete).toBe(true);
    expect(matchTemplateCriteria(agent, [{ ...data.criteria[0], criterion_text: 'Revised criterion' }]).matches.every((row) => !row)).toBe(true);
  });

  it('leaves revised criteria blank even when their IDs and positions are unchanged', () => {
    const data = result('coordinator');
    data.criteria = data.criteria.map((row, index) => index === 9
      ? { ...row, description: 'Content follows the revised program curriculum.' } : row);
    const mapping = matchTemplateCriteria('coordinator', data.criteria);
    expect(mapping.matches[9]).toBeNull();
    expect(mapping.complete).toBe(false);
  });

  it('does not mark ambiguous, missing or non-integer scores', () => {
    const data = result('gad');
    data.criteria = [...data.criteria,
      { ...data.criteria[0], criterion_id: 'duplicate' }].map((row, index) => index === 1
        ? { ...row, score: 0 } : index === 2 ? { ...row, score: 2.5 } : row);
    const mapping = matchTemplateCriteria('gad', data.criteria);
    expect(mapping.matches.slice(0, 3)).toEqual([null, null, null]);
    expect(mapping.complete).toBe(false);
    expect(matchTemplateCriteria('gad', []).complete).toBe(false);
  });

  it('preserves recorded ungrounded scores and totals with a review notice', async () => {
    const data = result('gad');
    data.criteria = data.criteria.map((row, index) => index === 0 ? { ...row, is_ungrounded: true } : row);
    expect(matchTemplateCriteria('gad', data.criteria).complete).toBe(true);
    const fields = filledFields(await exportPdf(data));
    expect(fields).toContain('(15) Tj');
    expect(fields).toContain('Evidence requires review: GAD-01.');
  });

  it('fills complete section totals but leaves the overall rating blank for changed criteria', async () => {
    const data = result('coordinator');
    data.criteria = data.criteria.map((row, index) => index === 9
      ? { ...row, criterion_text: 'Curriculum Alignment', description: 'Evaluate curriculum alignment.' } : row);
    const fields = filledFields(await exportPdf(data));
    expect(fields.match(/\(15\) Tj/g)).toHaveLength(1);
    expect(fields).not.toContain('(Satisfactory) Tj');
    expect(fields).toContain('Unavailable or changed criteria: A-05.');
  });

  it('calculates the printed average and rating from the printed scores', async () => {
    const data = result('sme');
    data.criteria = data.criteria.map((row, index) => ({ ...row, score: index < 5 ? 4 : 3 }));
    const fields = filledFields(await exportPdf(data));
    expect(fields).toContain('(20) Tj');
    expect(fields).toContain('(15) Tj');
    expect(fields).toContain('(3.50) Tj');
    expect(fields).toContain('(Very Satisfactory) Tj');
  });

  it('bounds long comments to the four existing lines without extra pages', async () => {
    const data = result('itso');
    data.summary = 'Learning materials need institutional review. '.repeat(250);
    const pdf = await exportPdf(data);
    expect(pdf.getPageCount()).toBe(1);
    const comments = filledFields(pdf).match(/73\. [^\n]+ Td\n\([^\n]+\) Tj/g);
    expect(comments).toHaveLength(4);
    expect(comments![3]).toContain('...');
    comments!.forEach((line, index) => {
      const y = Number(line.match(/73\. ([\d.]+) Td/)![1]);
      const template = SPECIALIST_PDF_TEMPLATES.itso;
      expect(template.height - y).toBeCloseTo(template.commentBaselines[index], 2);
    });
    expect(filledFields(pdf)).not.toContain('Saved rubric');
  });

  it('leaves failed scores blank and keeps long Unicode content on one page', async () => {
    const data = result('itso');
    data.evaluationStatus = 'FAILED';
    data.criteria = data.criteria.map((criterion) => ({
      ...criterion, justification: 'José: learning materials need institutional review. '.repeat(250),
    }));
    const bytes = await createSpecialistPdf(data, {
      templateBytes: await readFile(resolve(templateDirectory, 'itso.pdf')),
    });
    const pdf = await PDFDocument.load(bytes);
    expect(pdf.getPageCount()).toBe(1);
    expect(filledFields(pdf)).not.toContain('1.2 w');
  });

  it('does not fill scores on a failed domain even if the overall state says completed', async () => {
    const data = result('sme');
    data.status = 'ERROR';
    const fields = filledFields(await exportPdf(data));
    expect(fields).not.toContain('(15) Tj');
    expect(fields).toContain('Evaluation failed. Scores unavailable.');
    expect(fields).not.toContain('(Oct 5, 2026) Tj');
  });

  it('leaves the evaluation date blank when no valid completion date exists', async () => {
    const data = result('sme');
    data.evaluatedAt = 'invalid';
    expect(filledFields(await exportPdf(data))).not.toContain('(Invalid Date) Tj');
    data.evaluatedAt = null;
    expect(filledFields(await exportPdf(data))).not.toContain('(Oct 5, 2026) Tj');
  });
});
