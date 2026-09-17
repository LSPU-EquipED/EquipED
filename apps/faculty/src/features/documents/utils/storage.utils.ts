import type { ClientDocument } from '@equiped/types';

export type DocumentSortOption =
  | 'uploaded-desc'
  | 'uploaded-asc'
  | 'title-asc'
  | 'title-desc'
  | 'course-asc'
  | 'pages-desc';

export type StorageProgramFilter = 'ALL' | 'BSCS' | 'BSInfoTech';
export type StorageStatusFilter = 'all' | 'PROCESSED' | 'PROCESSING' | 'FAILED';

export interface StorageRepositoryMetrics {
  totalModules: number;
  totalIndexedPages: number;
  bscsCount: number;
  bsInfoTechCount: number;
  ocrVerifiedCount: number;
}

export function mapStatusToApi(filter: StorageStatusFilter): 'ready' | 'processing' | 'failed' | undefined {
  switch (filter) {
    case 'PROCESSED':
      return 'ready';
    case 'PROCESSING':
      return 'processing';
    case 'FAILED':
      return 'failed';
    default:
      return undefined;
  }
}

export function calculateStorageMetrics(
  documents: readonly ClientDocument[],
  totalModules: number,
): StorageRepositoryMetrics {
  let totalPages = 0;
  let bscs = 0;
  let bsInfoTech = 0;
  let ocrCount = 0;

  for (const doc of documents) {
    totalPages += doc.pageCount ?? 0;
    if (doc.program === 'BSCS') bscs += 1;
    else if (doc.program === 'BSInfoTech') bsInfoTech += 1;
    if (doc.hasOcrPages) ocrCount += 1;
  }

  return {
    totalModules,
    totalIndexedPages: totalPages,
    bscsCount: bscs,
    bsInfoTechCount: bsInfoTech,
    ocrVerifiedCount: ocrCount,
  };
}

export function sortDocuments<
  T extends {
    uploadedAt: string;
    title?: string | null;
    courseCode?: string | null;
    courseTitle?: string | null;
    pageCount?: number | null;
  },
>(documents: readonly T[], sortOption: DocumentSortOption): T[] {
  const list = [...documents];
  switch (sortOption) {
    case 'uploaded-desc':
      return list.sort((a, b) => new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime());
    case 'uploaded-asc':
      return list.sort((a, b) => new Date(a.uploadedAt).getTime() - new Date(b.uploadedAt).getTime());
    case 'title-asc':
      return list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    case 'title-desc':
      return list.sort((a, b) => (b.title || '').localeCompare(a.title || ''));
    case 'course-asc':
      return list.sort((a, b) => (a.courseCode || a.courseTitle || '').localeCompare(b.courseCode || b.courseTitle || ''));
    case 'pages-desc':
      return list.sort((a, b) => (b.pageCount ?? 0) - (a.pageCount ?? 0));
    default:
      return list;
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
