import type { PolicyArea, ReferenceSourceType } from '@/shared/types/documents';

export interface AdminUploadInput {
  file: File;
  sourceType: ReferenceSourceType | 'policy';
  title: string;
  program?: string;
  policyArea?: PolicyArea;
}
