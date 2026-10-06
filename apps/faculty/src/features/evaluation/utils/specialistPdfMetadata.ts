import { authApi, type AppAuthUser } from '@equiped/auth';
import { documentsApi } from '@equiped/api-client';
import { LSPU_SCC_COLLEGE_PROGRAMS, normalizeProgram, type ClientDocument } from '@equiped/types';
import type { ExportDomainData } from '../types';

/** Resolve metadata for the selected SLM, never substitute a module title for
 * a course title, or a program name for its college. */
export function resolveSpecialistPdfMetadata(
  data: ExportDomainData,
  document: ClientDocument | null,
  faculty: AppAuthUser | null,
): ExportDomainData {
  const program = normalizeProgram(data.program || document?.program || '');
  const college = LSPU_SCC_COLLEGE_PROGRAMS.find((group) =>
    group.programs.some((entry) => entry.code === program),
  );
  return {
    ...data,
    document,
    facultyName: data.facultyName || (faculty?.role === 'faculty' ? faculty.displayName : null),
    // Faculty evaluation results are owner-scoped to the account that submitted
    // the run. Do not use the module author's name as the evaluator's name.
    reviewer: data.reviewer || (faculty?.role === 'faculty' ? faculty.displayName : null),
    college: data.college || college?.code || null,
    courseTitle: data.courseTitle || document?.courseTitle || null,
    academicYear: data.academicYear || document?.academicYear || null,
    evaluatedAt: data.evaluatedAt || data.results?.completed_at || null,
  };
}

/** Load missing document details only when the user requests the export. The
 * existing API enforces ownership; unavailable records fail rather than export
 * another module's metadata. Reuse document data already loaded by the desk. */
export async function loadSpecialistPdfMetadata(data: ExportDomainData): Promise<ExportDomainData> {
  const documentId = data.results?.document_id || data.document?.documentId;
  const document = data.document && (!documentId || data.document.documentId === documentId)
    ? data.document
    : documentId ? await documentsApi.getDocument(documentId) : null;
  const session = (!data.facultyName || !data.reviewer) && documentId ? await authApi.me() : null;
  const faculty = session?.authenticated ? session.user : null;
  return resolveSpecialistPdfMetadata(data, document, faculty);
}
