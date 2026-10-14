import { Link } from "@tanstack/react-router";
import { CaretDown, FolderOpen } from "@phosphor-icons/react";
import { formatDateWithFallback } from "../utils/dateFormatting";

interface EvaluationResultMetadataProps {
  evaluationId: string;
  courseTitle?: string | null;
  uploadedAt?: string | null;
  rubricVersion?: number | null;
  formSnapshotId?: string | null;
  requiresCurriculum: boolean;
}

export function EvaluationResultMetadata({
  evaluationId,
  courseTitle,
  uploadedAt,
  rubricVersion,
  formSnapshotId,
  requiresCurriculum,
}: EvaluationResultMetadataProps) {
  const uploadDate = formatDateWithFallback(uploadedAt, "Not specified");
  const moduleDetails = [
    ...(courseTitle ? [["Course title", courseTitle]] : []),
    ...(uploadedAt ? [["Uploaded", uploadDate]] : []),
    ...(rubricVersion != null ? [["Rubric", `Revision ${rubricVersion}`]] : []),
    ...(requiresCurriculum ? [["Reference", "Institutional curriculum"]] : []),
  ];

  const metadata = (
    <div className="space-y-4 py-3">
      <dl className="space-y-4 text-xs">
        {moduleDetails.map(([label, value]) => (
          <div key={label} className="space-y-1">
            <dt className="text-text-muted">{label}</dt>
            <dd className="m-0 break-words font-medium leading-relaxed text-text">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <Link
        to="/documents"
        className="inline-flex min-h-8 items-center gap-1.5 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
      >
        <FolderOpen className="size-3.5" aria-hidden="true" />
        Module Library
      </Link>
      <details className="group/record mt-4 border-t border-border pt-3">
        <summary className="flex min-h-8 cursor-pointer list-none items-center justify-between gap-2 text-xs font-medium text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          Record details
          <CaretDown
            className="size-3.5 shrink-0 group-open/record:rotate-180"
            aria-hidden="true"
          />
        </summary>
        <dl className="mt-2 space-y-3 text-xs">
          <div>
            <dt className="text-text-muted">Evaluation ID</dt>
            <dd className="m-0 mt-1 break-all font-mono text-text">
              {evaluationId}
            </dd>
          </div>
          {formSnapshotId && (
            <div>
              <dt className="text-text-muted">Form snapshot</dt>
              <dd className="m-0 mt-1 break-all font-mono text-text">
                {formSnapshotId}
              </dd>
            </div>
          )}
        </dl>
      </details>
    </div>
  );

  return (
    <>
      <aside
        className="hidden min-w-0 border-r border-border pr-5 xl:block"
        aria-label="Evaluation metadata"
      >
        <h3 className="text-sm font-semibold text-text">Module details</h3>
        {metadata}
      </aside>
      <details className="group/metadata border-b border-border pb-3 xl:hidden">
        <summary className="flex min-h-8 cursor-pointer list-none items-center justify-between text-xs font-semibold text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          Module details
          <CaretDown
            className="size-4 group-open/metadata:rotate-180"
            aria-hidden="true"
          />
        </summary>
        {metadata}
      </details>
    </>
  );
}
