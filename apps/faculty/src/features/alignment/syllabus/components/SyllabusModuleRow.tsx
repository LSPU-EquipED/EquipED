import { Link } from "@tanstack/react-router";
import { ArrowRight } from "@phosphor-icons/react";
import { BUTTON_STYLES, cn } from "@equiped/ui";
import type { AlignmentSlmItem } from "../types";
import { isAlignmentActive, levelLabels } from "../utils/alignmentPresentation";

function checkStatus(item: AlignmentSlmItem) {
  const run = item.current_result;
  if (!run) return { label: "Not checked", color: "text-text-muted" };
  if (run.status === "FAILED")
    return { label: "Check failed", color: "text-destructive" };
  if (run.status === "QUEUED") return { label: "Queued", color: "text-info" };
  if (run.status === "RUNNING")
    return { label: "Checking syllabus", color: "text-info" };
  switch (run.alignment_level) {
    case "MEETS":
      return { label: "Meets syllabus", color: "text-success" };
    case "PARTIALLY_MEETS":
      return { label: levelLabels.PARTIALLY_MEETS, color: "text-warning" };
    case "DOES_NOT_MEET":
      return { label: levelLabels.DOES_NOT_MEET, color: "text-destructive" };
    default:
      return { label: "Result unavailable", color: "text-text-muted" };
  }
}

export function SyllabusModuleRow({ item }: { item: AlignmentSlmItem }) {
  const run = item.current_result;
  const status = checkStatus(item);
  const action =
    run?.status === "COMPLETED"
      ? "View result"
      : isAlignmentActive(run)
        ? "View progress"
        : run?.status === "FAILED"
          ? "Retry check"
          : "Set up check";
  const metadata = [item.course_code, item.program].filter(Boolean).join(" · ");
  const description = item.lesson_title || item.course_title;

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-surface-subtle/30 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_8rem] sm:gap-6 sm:px-6">
      <div className="col-span-2 min-w-0 sm:col-span-1">
        <h3 className="break-words text-sm font-semibold leading-relaxed text-text">
          {item.title}
        </h3>
        {description && description !== item.title && (
          <p className="mt-0.5 break-words text-sm leading-relaxed text-text-muted">
            {description}
          </p>
        )}
        {metadata && (
          <p className="mt-1 text-xs leading-relaxed text-text-muted">
            {metadata}
          </p>
        )}
      </div>
      <div className="min-w-0">
        <p className={cn("text-sm font-medium", status.color)}>
          {status.label}
        </p>
        {run?.syllabus_title && (
          <p className="mt-1 break-words text-xs leading-relaxed text-text-muted">
            {run.syllabus_title}
          </p>
        )}
      </div>
      <div className="justify-self-end">
        {item.evaluation_available ||
        run?.status === "COMPLETED" ||
        isAlignmentActive(run) ? (
          <Link
            to="/syllabus-alignment/$documentId"
            params={{ documentId: item.document_id }}
            aria-label={`${action} for ${item.title}`}
            className={cn(
              BUTTON_STYLES.base,
              "h-10 gap-2 whitespace-nowrap px-2 text-sm text-primary hover:bg-primary-soft",
            )}
          >
            {action}
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        ) : (
          <span className="text-xs text-text-muted">SLM not ready</span>
        )}
      </div>
    </li>
  );
}
