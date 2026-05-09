import { useMemo } from 'react';
import { getErrorMessage } from '@/shared/api/http';
import { useFetch } from '@/shared/hooks/useFetch';
import { uploadApi } from '../api/upload.api';

export function useUploadDocument() {
  const request = useFetch(uploadApi.uploadDocument);

  const errorMessage = useMemo(() => {
    return request.error ? getErrorMessage(request.error, 'Unable to upload the document.') : null;
  }, [request.error]);

  return {
    ...request,
    errorMessage,
    uploadDocument: request.execute,
  };
}
