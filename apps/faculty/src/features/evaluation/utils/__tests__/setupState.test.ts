import { describe, expect, it } from 'vitest';
import {
  buildEvaluationSubmitPayload,
  buildTargetedEvaluationSubmitPayload,
  normalizeProgram,
} from '../setupState';

describe('normalizeProgram - Canonical Constant Normalization', () => {
  it('canonicalizes BSCS variants to exact BSCS', () => {
    expect(normalizeProgram('BSCS')).toBe('BSCS');
    expect(normalizeProgram('  bscs ')).toBe('BSCS');
  });

  it('canonicalizes BSInfoTech, BSINFOTECH, BSIT, and bsit to exact canonical BSInfoTech', () => {
    expect(normalizeProgram('BSInfoTech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSINFOTECH')).toBe('BSInfoTech');
    expect(normalizeProgram('bsinfotech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSIT')).toBe('BSInfoTech');
    expect(normalizeProgram('  bsit  ')).toBe('BSInfoTech');
  });

  it('preserves other trimmed program strings', () => {
    expect(normalizeProgram('  BSIS  ')).toBe('BSIS');
  });
});

describe('buildEvaluationSubmitPayload - Single-Agent Evaluation Submissions', () => {
  it('builds valid SME submission payload without curriculum', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-slm-1',
      program: 'BSCS',
      targetAgent: 'sme',
    });

    expect(payload).toEqual({
      document_id: 'doc-slm-1',
      target_agent: 'sme',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
  });

  it('builds valid GAD submission payload without curriculum', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-slm-2',
      program: 'BSInfoTech',
      targetAgent: 'gad',
    });

    expect(payload).toEqual({
      document_id: 'doc-slm-2',
      target_agent: 'gad',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: false,
    });
  });

  it('builds valid ITSO submission payload without curriculum', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-slm-3',
      program: 'BSCS',
      targetAgent: 'itso',
    });

    expect(payload).toEqual({
      document_id: 'doc-slm-3',
      target_agent: 'itso',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
  });

  it('builds valid Coordinator submission payload with curriculum context', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-slm-4',
      program: 'BSCS',
      targetAgent: 'coordinator',
      curriculumId: 'curr-ready-1',
    });

    expect(payload).toEqual({
      document_id: 'doc-slm-4',
      curriculum_id: 'curr-ready-1',
      target_agent: 'coordinator',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
  });

  it('normalizes alias BSIT to canonical BSInfoTech on submission writes', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-slm-5',
      program: 'BSIT',
      targetAgent: 'gad',
    });

    expect(payload.confirmed_program).toBe('BSInfoTech');
  });

  it('throws when Coordinator evaluation lacks curriculum context', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-slm-6',
        program: 'BSCS',
        targetAgent: 'coordinator',
      }),
    ).toThrow('Curriculum context is required for Program Coordinator evaluation');

    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-slm-6',
        program: 'BSCS',
        targetAgent: 'coordinator',
        curriculumId: '   ',
      }),
    ).toThrow('Curriculum context is required for Program Coordinator evaluation');
  });

  it('throws on unsupported program write', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-slm-7',
        program: 'BSIS',
        targetAgent: 'sme',
      }),
    ).toThrow("Invalid program 'BSIS'");
  });

  it('buildTargetedEvaluationSubmitPayload alias matches exactly', () => {
    const p1 = buildEvaluationSubmitPayload({
      documentId: 'doc-1',
      program: 'BSCS',
      targetAgent: 'sme',
    });
    const p2 = buildTargetedEvaluationSubmitPayload({
      documentId: 'doc-1',
      program: 'BSCS',
      targetAgent: 'sme',
    });

    expect(p1).toEqual(p2);
  });
});
