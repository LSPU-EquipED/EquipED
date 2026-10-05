import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi, type AppAuthUser } from '@equiped/auth';
import { documentsApi } from '@equiped/api-client';
import type { ClientDocument } from '@equiped/types';
import type { ExportDomainData } from '../../types';
import { loadSpecialistPdfMetadata, resolveSpecialistPdfMetadata } from '../specialistPdfMetadata';

vi.mock('@equiped/auth', () => ({ authApi: { me: vi.fn() } }));
vi.mock('@equiped/api-client', () => ({ documentsApi: { getDocument: vi.fn() } }));

const faculty: AppAuthUser = { id: 'faculty-1', displayName: 'José Santos', email: 'jose@lspu.edu.ph', role: 'faculty' };
const document: ClientDocument = {
  documentId: 'slm-1', title: 'Lesson 1 module', courseTitle: 'Human-computer interaction',
  lessonTitle: 'Introduction', sourceType: 'slm', program: 'BSCS', academicYear: '2026-2027',
  courseCode: 'CS101', pageCount: 10, processingStatus: 'PROCESSED', hasOcrPages: false,
  uploadedAt: '2026-10-01T00:00:00Z', chunks: [],
};
const data: ExportDomainData = {
  agentId: 'sme', criteria: [], subtotal: 3, max_score: 4, status: 'OK',
  results: {
    evaluation_id: 'eval-1', document_id: 'slm-1', synthesized_score: 75,
    domain_scores: {}, flags: [], active_agents: ['sme'], failed_agents: [],
    is_partial: false, evaluation_status: 'COMPLETED', completed_at: '2026-10-05T07:30:00Z',
  },
};

describe('specialist PDF metadata', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(documentsApi.getDocument).mockResolvedValue(document);
    vi.mocked(authApi.me).mockResolvedValue({ authenticated: true, user: faculty });
  });

  it('fills faculty, course, college and academic year from their respective sources', async () => {
    const resolved = await loadSpecialistPdfMetadata(data);
    expect(documentsApi.getDocument).toHaveBeenCalledWith('slm-1');
    expect(resolved).toMatchObject({
      facultyName: 'José Santos', courseTitle: 'Human-computer interaction', college: 'CCS',
      academicYear: '2026-2027', evaluatedAt: '2026-10-05T07:30:00Z',
    });
    expect(resolved.reviewer).toBeUndefined();
  });

  it('reuses the selected desk document rather than fetching it again', async () => {
    await loadSpecialistPdfMetadata({ ...data, document });
    expect(documentsApi.getDocument).not.toHaveBeenCalled();
  });

  it('fetches the correct record when supplied document metadata belongs to another SLM', async () => {
    const resolved = await loadSpecialistPdfMetadata({ ...data, document: { ...document, documentId: 'other-slm' } });
    expect(documentsApi.getDocument).toHaveBeenCalledWith('slm-1');
    expect(resolved.document?.documentId).toBe('slm-1');
  });

  it('preserves explicitly provided faculty and document fields', async () => {
    const resolved = await loadSpecialistPdfMetadata({
      ...data, document, facultyName: 'Maria Cruz', college: 'CID', courseTitle: 'Confirmed course',
      academicYear: '2025-2026', evaluatedAt: '2026-09-15',
    });
    expect(resolved).toMatchObject({
      facultyName: 'Maria Cruz', college: 'CID', courseTitle: 'Confirmed course',
      academicYear: '2025-2026', evaluatedAt: '2026-09-15',
    });
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('does not substitute an administrator name, unknown program, or module title', () => {
    const resolved = resolveSpecialistPdfMetadata(data,
      { ...document, courseTitle: null, academicYear: null, program: 'Unknown' },
      { ...faculty, role: 'admin' });
    expect(resolved).toMatchObject({ facultyName: null, college: null, courseTitle: null, academicYear: null });
  });

  it('does not fill a faculty name from an unauthenticated session', async () => {
    vi.mocked(authApi.me).mockResolvedValue({ authenticated: false, user: null });
    expect((await loadSpecialistPdfMetadata(data)).facultyName).toBeNull();
  });

  it('does not export substituted metadata when the selected module is inaccessible', async () => {
    vi.mocked(documentsApi.getDocument).mockRejectedValue(new Error('Document not found'));
    await expect(loadSpecialistPdfMetadata(data)).rejects.toThrow('Document not found');
    expect(authApi.me).not.toHaveBeenCalled();
  });
});
