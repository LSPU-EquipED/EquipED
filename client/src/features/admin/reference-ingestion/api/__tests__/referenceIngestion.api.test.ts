import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '@/shared/api/http';
import {
  isCanonicalReferenceProgram,
  referenceIngestionApi,
} from '../referenceIngestion.api';

describe('isCanonicalReferenceProgram', () => {
  it('accepts exact canonical BSCS and BSInfoTech', () => {
    expect(isCanonicalReferenceProgram('BSCS')).toBe(true);
    expect(isCanonicalReferenceProgram('BSInfoTech')).toBe(true);
  });

  it('rejects non-canonical values without emitting BSIT', () => {
    expect(isCanonicalReferenceProgram('BSIT')).toBe(false);
    expect(isCanonicalReferenceProgram('bsit')).toBe(false);
    expect(isCanonicalReferenceProgram('BSINFOTECH')).toBe(false);
    expect(isCanonicalReferenceProgram('bscs')).toBe(false);
    expect(isCanonicalReferenceProgram('OTHER')).toBe(false);
    expect(isCanonicalReferenceProgram(undefined)).toBe(false);
    expect(isCanonicalReferenceProgram(null)).toBe(false);
    expect(isCanonicalReferenceProgram('')).toBe(false);
  });
});

describe('referenceIngestionApi.uploadReferenceDocument', () => {
  it('submits source_type=curriculum with canonical BSCS in FormData', async () => {
    const dummyFile = new File(['dummy content'], 'curriculum.pdf', { type: 'application/pdf' });
    let capturedFormData: FormData | null = null;

    const mockResponse = {
      document_id: 'doc-curr-1',
      title: 'BSCS Curriculum 2026',
      source_type: 'curriculum',
      processing_status: 'PROCESSING' as const,
      academic_year: null,
      course_code: null,
      course_title: null,
      lesson_title: null,
    };

    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (_url: string, options?: RequestInit) => {
      capturedFormData = options?.body as FormData;
      return mockResponse;
    });

    const result = await referenceIngestionApi.uploadReferenceDocument({
      file: dummyFile,
      sourceType: 'curriculum',
      title: 'BSCS Curriculum 2026',
      program: 'BSCS',
    });

    expect(spy).toHaveBeenCalledWith('/documents/upload', expect.objectContaining({ method: 'POST' }));
    expect(capturedFormData).not.toBeNull();
    const data = capturedFormData as unknown as FormData;
    expect(data.get('source_type')).toBe('curriculum');
    expect(data.get('title')).toBe('BSCS Curriculum 2026');
    expect(data.get('program')).toBe('BSCS');
    expect(data.get('policy_area')).toBeNull();
    expect(result.documentId).toBe('doc-curr-1');
    expect(result.sourceType).toBe('curriculum');

    spy.mockRestore();
  });

  it('submits source_type=curriculum with canonical BSInfoTech in FormData', async () => {
    const dummyFile = new File(['dummy content'], 'curriculum_it.pdf', { type: 'application/pdf' });
    let capturedFormData: FormData | null = null;

    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (_url: string, options?: RequestInit) => {
      capturedFormData = options?.body as FormData;
      return {
        document_id: 'doc-curr-2',
        title: 'BSInfoTech Curriculum',
        source_type: 'curriculum',
        processing_status: 'PROCESSING' as const,
        academic_year: null,
        course_code: null,
        course_title: null,
        lesson_title: null,
      };
    });

    await referenceIngestionApi.uploadReferenceDocument({
      file: dummyFile,
      sourceType: 'curriculum',
      title: 'BSInfoTech Curriculum',
      program: 'BSInfoTech',
    });

    const data = capturedFormData as unknown as FormData;
    expect(data.get('program')).toBe('BSInfoTech');

    spy.mockRestore();
  });

  it('rejects non-canonical program on curriculum upload without conversion or BSIT emission', async () => {
    const dummyFile = new File(['dummy content'], 'curriculum_bad.pdf', { type: 'application/pdf' });

    await expect(
      referenceIngestionApi.uploadReferenceDocument({
        file: dummyFile,
        sourceType: 'curriculum',
        title: 'Invalid Curriculum',
        program: 'BSIT',
      }),
    ).rejects.toThrow(/Invalid curriculum program/);
  });

  it('submits source_type=syllabus with canonical program in FormData', async () => {
    const dummyFile = new File(['dummy content'], 'syllabus_cs.pdf', { type: 'application/pdf' });
    let capturedFormData: FormData | null = null;

    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (_url: string, options?: RequestInit) => {
      capturedFormData = options?.body as FormData;
      return {
        document_id: 'doc-syl-2',
        title: 'CS 101 Syllabus',
        source_type: 'syllabus',
        processing_status: 'PROCESSING' as const,
        program: 'BSCS',
        academic_year: null,
        course_code: null,
        course_title: null,
        lesson_title: null,
      };
    });

    await referenceIngestionApi.uploadReferenceDocument({
      file: dummyFile,
      sourceType: 'syllabus',
      title: 'CS 101 Syllabus',
      program: 'BSCS',
    });

    const data = capturedFormData as unknown as FormData;
    expect(data.get('source_type')).toBe('syllabus');
    expect(data.get('title')).toBe('CS 101 Syllabus');
    expect(data.get('program')).toBe('BSCS');

    spy.mockRestore();
  });

  it('rejects non-canonical program on syllabus upload with client validation error', async () => {
    const dummyFile = new File(['dummy content'], 'syllabus_bad.pdf', { type: 'application/pdf' });

    await expect(
      referenceIngestionApi.uploadReferenceDocument({
        file: dummyFile,
        sourceType: 'syllabus',
        title: 'CS 101 Syllabus',
        program: 'BSIT',
      }),
    ).rejects.toThrow(/Invalid reference program 'BSIT'/);
  });

  it('submits source_type=syllabus without program or policy_area', async () => {
    const dummyFile = new File(['dummy content'], 'syllabus.pdf', { type: 'application/pdf' });
    let capturedFormData: FormData | null = null;

    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (_url: string, options?: RequestInit) => {
      capturedFormData = options?.body as FormData;
      return {
        document_id: 'doc-syl-1',
        title: 'CS 101 Syllabus',
        source_type: 'syllabus',
        processing_status: 'PROCESSING' as const,
        program: null,
        academic_year: null,
        course_code: null,
        course_title: null,
        lesson_title: null,
      };
    });

    await referenceIngestionApi.uploadReferenceDocument({
      file: dummyFile,
      sourceType: 'syllabus',
      title: 'CS 101 Syllabus',
    });

    const data = capturedFormData as unknown as FormData;
    expect(data.get('source_type')).toBe('syllabus');
    expect(data.get('title')).toBe('CS 101 Syllabus');
    expect(data.get('program')).toBeNull();
    expect(data.get('policy_area')).toBeNull();

    spy.mockRestore();
  });

  it('submits source_type=policy with policy_area', async () => {
    const dummyFile = new File(['dummy content'], 'policy.pdf', { type: 'application/pdf' });
    let capturedFormData: FormData | null = null;

    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (_url: string, options?: RequestInit) => {
      capturedFormData = options?.body as FormData;
      return {
        document_id: 'doc-pol-1',
        title: 'IP Policy 2026',
        source_type: 'policy',
        processing_status: 'PROCESSING' as const,
        program: null,
        academic_year: null,
        course_code: null,
        course_title: null,
        lesson_title: null,
      };
    });

    await referenceIngestionApi.uploadReferenceDocument({
      file: dummyFile,
      sourceType: 'policy',
      title: 'IP Policy 2026',
      policyArea: 'intellectual_property',
    });

    const data = capturedFormData as unknown as FormData;
    expect(data.get('source_type')).toBe('policy');
    expect(data.get('policy_area')).toBe('intellectual_property');

    spy.mockRestore();
  });
});
