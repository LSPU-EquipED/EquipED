import { Check, Circle, ClipboardText } from '@phosphor-icons/react';
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
  const checks = [
    { label: 'Reference type selected', complete: Boolean(sourceType) },
    ...(isCurriculum
      ? [{ label: 'Program assigned', complete: program.trim().length > 0 }]
      : []),
    ...(isPolicyAreaRequired
      ? [{ label: 'Policy area assigned', complete: true }]
      : []),
    { label: 'Title added', complete: title.trim().length > 0 },
    { label: 'PDF selected', complete: Boolean(file) },
  ];

  return (
    <section className="rounded-md border border-border bg-surface p-5">
      <div className="flex items-start gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-primary-soft text-primary">
          <ClipboardText className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-text">Readiness</h2>
          <p className="mt-0.5 text-xs leading-relaxed text-text-muted">
            Complete the required details before submission.
          </p>
        </div>
      </div>

      <ul className="mt-5 divide-y divide-border border-y border-border">
        {checks.map((check) => (
          <li key={check.label} className="flex items-center gap-2.5 py-3 text-sm">
            {check.complete ? (
              <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-success-soft text-success">
                <Check className="size-3" weight="bold" aria-hidden="true" />
              </span>
            ) : (
              <Circle className="size-4 shrink-0 text-border-strong" aria-hidden="true" />
            )}
            <span className={check.complete ? 'text-text' : 'text-text-muted'}>{check.label}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs leading-relaxed text-text-muted">
        References are processed locally and become available in the library after ingestion.
      </p>
    </section>
  );
}
