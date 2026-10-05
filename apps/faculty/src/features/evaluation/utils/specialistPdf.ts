import { TARGET_AGENT_META, isTargetAgent } from '@equiped/types';
import type { ExportDomainData, ExportAgentId } from '../types';
import { adjectivalRating, cleanJustification, formatScore } from './scoreHelpers';
import { matchTemplateCriteria, SPECIALIST_PDF_TEMPLATES } from './specialistPdfTemplates';
import { formatDateWithFallback } from './dateFormatting';

type ExportAssets = { templateBytes: Uint8Array };
const FILLED_FONT_SIZE = 12;

function exportState(data: ExportDomainData): string {
  const state = data.evaluationStatus ?? data.results?.evaluation_status ?? data.status;
  if (state === 'FAILED' || data.results?.evaluation_status === 'FAILED'
    || ['ERROR', 'FAILED'].includes(data.status) || data.results?.failed_agents?.includes(data.agentId)) {
    return 'Failed';
  }
  if ((state === 'COMPLETED' || state === 'OK') && (data.isPartial || data.results?.is_partial)) {
    return 'Intentional partial evaluation';
  }
  return state === 'COMPLETED' || state === 'OK' ? 'Completed' : state || 'Unavailable';
}

/** Preserve the original PDF as vector content; add a transparent score overlay
 * in its existing fields. The source form is never redrawn or extended. */
export async function createSpecialistPdf(data: ExportDomainData, assets: ExportAssets): Promise<Uint8Array> {
  if (!isTargetAgent(data.agentId)) throw new Error('Unknown specialist PDF template.');
  const agent: ExportAgentId = data.agentId;
  const layout = SPECIALIST_PDF_TEMPLATES[agent];
  const [{ jsPDF }, { PDFDocument }] = await Promise.all([
    import('jspdf'), import('pdf-lib'),
  ]);
  const source = await PDFDocument.load(assets.templateBytes);
  if (source.getPageCount() !== 1) throw new Error('Unexpected institutional template page count.');
  const original = source.getPage(0);
  if (Math.abs(original.getWidth() - layout.width) > 0.1 || Math.abs(original.getHeight() - layout.height) > 0.1) {
    throw new Error('Institutional template dimensions do not match the field layout.');
  }
  const pdf = new jsPDF({ unit: 'pt', format: [layout.width, layout.height] });
  // PDF's standard Times face matches the institutional serif styling without
  // substituting the sans-serif font used by the other report exports.
  const text = (value: string, x: number, y: number, width: number, align: 'left' | 'center' = 'left') => {
    pdf.setFont('times', 'normal');
    pdf.setFontSize(FILLED_FONT_SIZE);
    let fitted = cleanJustification(value).replace(/\s+/g, ' ').trim();
    if (pdf.getTextWidth(fitted) > width) {
      while (fitted && pdf.getTextWidth(`${fitted}...`) > width) fitted = fitted.slice(0, -1);
      fitted += '...';
    }
    pdf.text(fitted, align === 'center' ? x + width / 2 : x, y, { align });
  };
  const metadata = {
    faculty: data.facultyName || '',
    college: data.college || '',
    course: data.courseTitle || data.document?.courseTitle || '',
    semester: data.semester || '',
    year: data.academicYear || data.document?.academicYear || '',
  };
  const state = exportState(data);
  pdf.setTextColor(0, 0, 0);
  const facultyWidth = agent === 'sme' ? 204 : 232;
  text(metadata.faculty, 166, 161, facultyWidth - 5);
  text(metadata.college, agent === 'sme' ? 419 : 447, 161, agent === 'sme' ? 104 : 76);
  text(metadata.course, 145, 175, 119);
  text(metadata.semester, 336, 175, 34);
  text(metadata.year, 465, 175, 59);

  const mapping = matchTemplateCriteria(agent, data.criteria);
  const canMark = state === 'Completed' || state === 'Intentional partial evaluation';
  if (canMark) {
    // Keep the human reviewer line blank. The date is the saved evaluation
    // completion, never the download date or an inferred signing date.
    const [dateX, dateY, dateRight] = layout.evaluatedDateLine;
    text(formatDateWithFallback(data.evaluatedAt || data.results?.completed_at, ''),
      dateX + 4, dateY - 2, dateRight - dateX - 8, 'center');
    pdf.setDrawColor(27, 59, 135);
    pdf.setLineWidth(1.2);
    mapping.matches.forEach((criterion, index) => {
      if (!criterion) return;
      const [x, y] = layout.rows[index].scoreCenters[4 - criterion.score];
      pdf.circle(x, y, 6);
    });
    // Each printed section can total independently; the overall average needs
    // every source criterion, even if the saved rubric has a different size.
    layout.totals.forEach((cell, index) => {
      const section = mapping.matches.slice(index * 5, index * 5 + 5);
      if (section.some((item) => !item)) return;
      const total = section.reduce((sum, item) => sum + item!.score, 0);
      text(String(total), cell[0] + 8, (cell[1] + cell[3]) / 2 + 3, cell[2] - cell[0] - 16);
    });
    if (mapping.complete) {
      const average = mapping.matches.reduce((sum, item) => sum + item!.score, 0) / mapping.matches.length;
      // Raised baselines keep the values clear of their printed rules.
      text(formatScore(average), 457, layout.averageY - 2, 66);
      // The original form averages its printed rows. Its rating must describe
      // that average, not a potentially weighted saved domain subtotal.
      text(adjectivalRating(average), layout.ratingX + 2, layout.ratingY - 2, 524 - layout.ratingX);
    }
  }

  const notices: string[] = [];
  if (!canMark) {
    notices.push(state === 'Failed' ? 'Evaluation failed. Scores unavailable.' : 'Evaluation not complete. Scores unavailable.');
  } else {
    const unmatched = layout.rows.filter((_, index) => !mapping.matches[index]).map((row) => row.criterionCode);
    if (unmatched.length) notices.push(`Unavailable or changed criteria: ${unmatched.join(', ')}. Review required.`);
    if (!mapping.complete && !unmatched.length) notices.push('Saved rubric includes additional criteria. Overall rating unavailable.');
    const ungrounded = layout.rows.filter((_, index) => mapping.matches[index]?.is_ungrounded).map((row) => row.criterionCode);
    if (ungrounded.length) notices.push(`Evidence requires review: ${ungrounded.join(', ')}.`);
    if (data.summary) notices.push(cleanJustification(data.summary));
  }
  // Use only the four comment lines already on the institutional form. Never
  // spill a narrative into signatures or create an extra results page.
  pdf.setFont('times', 'normal');
  pdf.setFontSize(FILLED_FONT_SIZE);
  const lines: string[] = pdf.splitTextToSize(notices.join(' ').replace(/\s+/g, ' ').trim(), 449);
  const visibleLines = lines.slice(0, layout.commentBaselines.length);
  if (lines.length > visibleLines.length) {
    const last = visibleLines.length - 1;
    visibleLines[last] = `${visibleLines[last].replace(/\s+\S*$/, '')}...`;
  }
  visibleLines.forEach((line, index) => text(line, 73, layout.commentBaselines[index], 449));

  const overlayBytes = pdf.output('arraybuffer');
  const [overlay] = await source.embedPdf(overlayBytes, [0]);
  original.drawPage(overlay, { x: 0, y: 0, width: layout.width, height: layout.height });
  source.setTitle(`${layout.code} - ${TARGET_AGENT_META[agent].shortLabel} advisory evaluation`);
  source.setCreator('EquipED');
  return source.save();
}

export async function downloadSpecialistPdf(data: ExportDomainData): Promise<void> {
  if (!isTargetAgent(data.agentId)) throw new Error('Unknown specialist PDF template.');
  const template = SPECIALIST_PDF_TEMPLATES[data.agentId];
  const response = await fetch(template.url);
  if (!response.ok) throw new Error('The institutional PDF template could not be loaded.');
  const bytes = await createSpecialistPdf(data, { templateBytes: new Uint8Array(await response.arrayBuffer()) });
  const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${template.code}-${data.agentId}-evaluation.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
