import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type DragEvent } from 'react';
import { documentsApi } from '@/shared/api/documents.api';
import { normalizeProgram } from '@/shared/constants/programs';
import type { DocumentUploadResponse, PolicyArea } from '@/shared/types/documents';
import { useAdminUpload } from './useAdminUpload';
import type { AdminUploadSourceType } from '../types';

const POLL_INTERVAL_MS = 4000;

export function useAdminUploadFlow() {
  const { uploadDocument, isLoading, errorMessage, setData: resetUpload } = useAdminUpload();
  const [sourceType, setSourceType] = useState<AdminUploadSourceType>('syllabus');
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('');
  const [policyArea, setPolicyArea] = useState<PolicyArea>('general_itso');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const [programTouched, setProgramTouched] = useState(false);
  const [formAttempted, setFormAttempted] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isCurriculum = sourceType === 'curriculum';
  const isPolicyAreaRequired = sourceType === 'policy';
  const isProgramInvalid = isCurriculum && (programTouched || formAttempted) && !program.trim();
  const canSubmit =
    !!file &&
    title.trim().length > 0 &&
    (!isCurriculum || !!program.trim()) &&
    (!isPolicyAreaRequired || !!policyArea);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setUploadResult(null);
    resetUpload(null);
    setFileValidationError(null);

    if (nextFile && !title.trim()) {
      setTitle(nextFile.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0] ?? null;
    if (!droppedFile) return;

    if (!droppedFile.name.toLowerCase().endsWith('.pdf') && droppedFile.type !== 'application/pdf') {
      setFileValidationError('Only PDF documents are supported for reference ingestion.');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setFileValidationError(null);
    setFile(droppedFile);
    setUploadResult(null);
    resetUpload(null);

    if (!title.trim()) {
      setTitle(droppedFile.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleSourceTypeChange = (next: AdminUploadSourceType) => {
    setSourceType(next);
    setProgram('');
    setPolicyArea('general_itso');
    setUploadResult(null);
    setProgramTouched(false);
    setFormAttempted(false);
    resetUpload(null);
  };

  const handleProgramChange = (val: string) => {
    setProgramTouched(true);
    setProgram(normalizeProgram(val));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormAttempted(true);

    if (!file || !title.trim()) {
      return;
    }

    if (isCurriculum && !program.trim()) {
      return;
    }

    if (isPolicyAreaRequired && !policyArea) {
      return;
    }

    setUploadResult(null);

    try {
      const result = await uploadDocument({
        file,
        sourceType,
        title,
        program: isCurriculum ? program.trim() : undefined,
        policyArea: isPolicyAreaRequired ? policyArea : undefined,
      });
      setUploadResult({
        ...result,
        program: isCurriculum ? program.trim() : null,
      });
    } catch {
      // Error state is surfaced via errorMessage from the hook
    }
  };

  // Reference documents return PROCESSING immediately — poll background task until PROCESSED/FAILED
  useEffect(() => {
    if (!uploadResult || uploadResult.processingStatus !== 'PROCESSING') {
      return;
    }

    let cancelled = false;
    const documentId = uploadResult.documentId;

    const poll = async () => {
      try {
        const doc = await documentsApi.getDocument(documentId);
        if (cancelled) return;
        if (doc.processingStatus !== 'PROCESSING') {
          const firstWarning = doc.processingWarnings?.find(
            (warning) => typeof warning === 'string' && warning.trim().length > 0,
          )?.trim();
          const fallbackError =
            'Document processing failed. Please verify the uploaded reference and try again.';
          const failedErrorMessage =
            doc.processingStatus === 'FAILED' ? firstWarning || fallbackError : undefined;

          setUploadResult((previous) =>
            previous
              ? {
                  ...previous,
                  processingStatus: doc.processingStatus,
                  academicYear: doc.academicYear,
                  courseCode: doc.courseCode,
                  program: doc.program ?? previous.program,
                  errorMessage: failedErrorMessage ?? previous.errorMessage,
                }
              : previous,
          );
        }
      } catch {
        // transient poll failure — try again on the next tick
      }
    };

    void poll();
    const intervalId = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [uploadResult]);

  const handleReset = () => {
    setUploadResult(null);
    resetUpload(null);
    setFile(null);
    setTitle('');
    setProgram('');
    setPolicyArea('general_itso');
    setProgramTouched(false);
    setFormAttempted(false);
    setFileValidationError(null);
    setIsDragging(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return {
    sourceType,
    handleSourceTypeChange,
    program,
    handleProgramChange,
    isProgramInvalid,
    policyArea,
    setPolicyArea,
    title,
    setTitle,
    file,
    fileInputRef,
    isDragging,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileChange,
    fileValidationError,
    isLoading,
    canSubmit,
    handleReset,
    handleSubmit,
    isCurriculum,
    isPolicyAreaRequired,
    errorMessage,
    uploadResult,
  };
}
