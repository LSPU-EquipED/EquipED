import { useMemo } from 'react';
import { getErrorMessage } from '@/shared/api/http';
import { useFetch } from '@/shared/hooks/useFetch';
import { adminApi } from '../api/admin.api';

export function useAdminUpload() {
  const request = useFetch(adminApi.uploadReferenceDocument);

  const errorMessage = useMemo(() => {
    return request.error ? getErrorMessage(request.error, 'Unable to upload the document.') : null;
  }, [request.error]);

  return {
    ...request,
    errorMessage,
    uploadDocument: request.execute,
  };
}
