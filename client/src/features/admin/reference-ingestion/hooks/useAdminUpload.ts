import { useMemo } from 'react';
import { getErrorMessage } from '@/shared/api/http';
import { useFetch } from '@/shared/hooks/useFetch';
import { referenceIngestionApi } from '../api/referenceIngestion.api';

export function useAdminUpload() {
  const request = useFetch(referenceIngestionApi.uploadReferenceDocument);

  const errorMessage = useMemo(() => {
    return request.error ? getErrorMessage(request.error, 'Unable to upload the document.') : null;
  }, [request.error]);

  return {
    ...request,
    errorMessage,
    uploadDocument: request.execute,
  };
}
