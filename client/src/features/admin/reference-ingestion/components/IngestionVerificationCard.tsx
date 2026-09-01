import { CheckCircle, FilePdf, ShieldCheck } from '@phosphor-icons/react';
import type { AdminUploadSourceType } from '../types';

interface IngestionVerificationCardProps {
  file: File | null;
  sourceType: AdminUploadSourceType;
  title: string;
  isCurriculum: boolean;
  program: string;
  isPolicyAreaRequired: boolean;
}

export function IngestionVerificationCard({
  file,
  sourceType,
  title,
  isCurriculum,
  program,
  isPolicyAreaRequired,
}: IngestionVerificationCardProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-6 space-y-5 shadow-none">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-text tracking-tight">
          Ingestion Verification
        </h2>
        <ShieldCheck className="size-5 text-primary" aria-hidden="true" />
      </div>

      {/* File Inspection Summary */}
      <div className="rounded-sm border border-border bg-surface-subtle p-4 space-y-2.5 text-xs">
        <div className="flex items-center gap-2">
          <FilePdf className="size-4 text-primary shrink-0" aria-hidden="true" />
          <span className="font-semibold text-text truncate">
            {file ? file.name : 'No file selected yet'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-text-muted font-medium pt-1">
          <div>
            <span className="text-text-muted">Target:</span>{' '}
            <span className="font-semibold text-text capitalize">{sourceType}</span>
          </div>
          <div>
            <span className="text-text-muted">Size:</span>{' '}
            <span className="font-semibold text-text tabular-nums">
              {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Checklist */}
      <div className="space-y-2.5 text-xs">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Pre-Ingestion Checklist
        </p>
        <ul className="space-y-2 text-[11px] text-text font-medium">
          <li className="flex items-center gap-2">
            {file ? (
              <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
            ) : (
              <span className="size-3.5 rounded-full border border-border shrink-0" />
            )}
            <span>Valid PDF document selected</span>
          </li>
          <li className="flex items-center gap-2">
            {title.trim().length > 0 ? (
              <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
            ) : (
              <span className="size-3.5 rounded-full border border-border shrink-0" />
            )}
            <span>Descriptive document title assigned</span>
          </li>
          {isCurriculum ? (
            <li className="flex items-center gap-2">
              {program.trim().length > 0 ? (
                <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
              ) : (
                <span className="size-3.5 rounded-full border border-border shrink-0" />
              )}
              <span>Associated with BSCS or BSInfoTech</span>
            </li>
          ) : null}
          {isPolicyAreaRequired ? (
            <li className="flex items-center gap-2">
              <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
              <span>Policy classification area assigned</span>
            </li>
          ) : null}
        </ul>
      </div>

      {/* Grounding Notice */}
      <p className="text-xs text-text-muted leading-relaxed pt-2">
        Reference documents are stored in local storage, chunked semantically, and embedded into local ChromaDB vectors for retrieval during multi-agent evaluations.
      </p>
    </div>
  );
}
