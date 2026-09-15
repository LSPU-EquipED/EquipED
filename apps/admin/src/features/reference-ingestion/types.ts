import type { PolicyArea, ReferenceSourceType } from '@equiped/types';

export type AdminUploadSourceType = ReferenceSourceType | 'policy';

export interface AdminUploadInput {
  file: File;
  sourceType: AdminUploadSourceType;
  title: string;
  program?: string;
  policyArea?: PolicyArea;
}
