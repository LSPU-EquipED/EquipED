import { Link } from "@tanstack/react-router";
import { FolderOpen } from "@phosphor-icons/react";
import { formatDateWithFallback } from "../../utils/dateFormatting";

interface EvaluationResultMetadataProps {
  courseTitle?: string | null;
  uploadedAt?: string | null;
  rubricVersion?: number | null;
  requiresCurriculum: boolean;
}

export function EvaluationResultMetadata({
  courseTitle,
  uploadedAt,
  rubricVersion,
  requiresCurriculum,
}: EvaluationResultMetadataProps) {
  const moduleDetails = [
    ...(courseTitle ? [["Course title", courseTitle]] : []),
    ...(uploadedAt
      ? [["Uploaded", formatDateWithFallback(uploadedAt, "Not specified")]]
      : []),
    ...(rubricVersion != null ? [["Rubric", `Revision ${rubricVersion}`]] : []),
    ...(requiresCurriculum ? [["Reference", "Institutional curriculum"]] : []),
  ];

  return (
    <section className="er-metadata" aria-label="Evaluation metadata">
      <dl className="er-metadata-fields">
        {moduleDetails.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <Link to="/documents" className="er-library-link">
        <FolderOpen size={15} aria-hidden="true" />
        Module Library
      </Link>
    </section>
  );
}

export function EvaluationRecordMetadata({
  evaluationId,
  formSnapshotId,
}: {
  evaluationId: string;
  formSnapshotId?: string | null;
}) {
  return (
    <footer className="er-record" aria-label="Evaluation record">
      <dl className="er-metadata-fields">
        <div>
          <dt>Evaluation ID</dt>
          <dd className="font-mono">{evaluationId}</dd>
        </div>
        {formSnapshotId && (
          <div>
            <dt>Form snapshot</dt>
            <dd className="font-mono">{formSnapshotId}</dd>
          </div>
        )}
      </dl>
    </footer>
  );
}
