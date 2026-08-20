import { describe, expect, it } from 'vitest';
import { formatDate, getStatusMeta, sourceTypeLabels } from '../document.utils';

describe('document.utils', () => {
  it('maps PROCESSED status to Ready with accessible contrast badge class', () => {
    const meta = getStatusMeta('PROCESSED');
    expect(meta.label).toBe('Ready');
    expect(meta.badgeClass).toContain('bg-[#166534]');
    expect(meta.badgeClass).toContain('text-white');
  });

  it('maps PENDING and PROCESSING statuses correctly', () => {
    const pending = getStatusMeta('PENDING');
    expect(pending.label).toBe('Processing');
    expect(pending.badgeClass).toContain('bg-[#f2c811]');

    const processing = getStatusMeta('PROCESSING');
    expect(processing.label).toBe('Processing');
  });

  it('maps FAILED status correctly', () => {
    const failed = getStatusMeta('FAILED');
    expect(failed.label).toBe('Failed');
    expect(failed.badgeClass).toContain('bg-[#b91c1c]');
  });

  it('returns fallback for unknown statuses', () => {
    const fallback = getStatusMeta('NON_EXISTENT');
    expect(fallback.label).toBe('Unavailable');
    expect(fallback.badgeClass).toContain('bg-slate-600');
  });

  it('formats dates consistently', () => {
    const formatted = formatDate('2026-08-15T14:30:00Z');
    expect(formatted).toMatch(/\d{2}\/\d{2}\/\d{4}/);
  });

  it('defines source type labels for all expected document types', () => {
    expect(sourceTypeLabels.slm).toBe('SLM');
    expect(sourceTypeLabels.syllabus).toBe('Syllabus');
    expect(sourceTypeLabels.rubric_sme).toBe('SME Rubric');
    expect(sourceTypeLabels.curriculum).toBe('Curriculum');
  });
});
