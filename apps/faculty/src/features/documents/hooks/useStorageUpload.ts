import { useState, useRef, type DragEvent, type FormEvent, useEffect, type RefObject } from 'react';
import { documentsApi, getErrorMessage } from '@equiped/api-client';

interface UseStorageUploadOptions {
  isOpen: boolean;
  onSuccess: () => void;
}

export interface UseStorageUploadReturn {
  file: File | null;
  title: string;
  setTitle: (title: string) => void;
  program: string;
  setProgram: (program: string) => void;
  isDragging: boolean;
  setIsDragging: (dragging: boolean) => void;
  isUploading: boolean;
  error: string | null;
  fileInputRef: RefObject<HTMLInputElement>;
  handleFileChange: (selected: File | null) => void;
  handleDrop: (e: DragEvent<HTMLLabelElement>) => void;
  handleSubmit: (e: FormEvent) => Promise<void>;
}

export function useStorageUpload({ isOpen, onSuccess }: UseStorageUploadOptions): UseStorageUploadReturn {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [program, setProgram] = useState('BSCS');
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset form state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setTitle('');
      setProgram('BSCS');
      setError(null);
      setIsDragging(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen]);

  const handleFileChange = (selected: File | null) => {
    setError(null);
    if (!selected) {
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }
    if (!selected.name.toLowerCase().endsWith('.pdf') && selected.type !== 'application/pdf') {
      setError('Only PDF documents (.pdf) are supported for course SLM storage.');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }
    if (selected.size > 50 * 1024 * 1024) {
      setError('The selected PDF exceeds the 50 MB limit. Please select a smaller file.');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }
    setFile(selected);
    if (!title.trim()) {
      setTitle(selected.name.replace(/\.pdf$/i, ''));
    }
  };

  const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) handleFileChange(dropped);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || !title.trim() || !program) return;
    setIsUploading(true);
    setError(null);

    try {
      await documentsApi.uploadDocument({
        file,
        sourceType: 'slm',
        title: title.trim(),
        program,
      });
      setIsUploading(false);
      onSuccess();
    } catch (err) {
      setIsUploading(false);
      setError(getErrorMessage(err, 'Failed to upload SLM document to storage.'));
    }
  };

  return {
    file,
    title,
    setTitle,
    program,
    setProgram,
    isDragging,
    setIsDragging,
    isUploading,
    error,
    fileInputRef,
    handleFileChange,
    handleDrop,
    handleSubmit,
  };
}
