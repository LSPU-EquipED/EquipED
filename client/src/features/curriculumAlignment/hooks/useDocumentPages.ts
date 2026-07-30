import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useDocumentPages(checkId: string | null) {
  return useQuery({
    queryKey: ['curriculum-map', 'document-pages', checkId],
    queryFn: () => curriculumAlignmentApi.getDocumentPages(checkId as string),
    enabled: !!checkId,
  });
}
