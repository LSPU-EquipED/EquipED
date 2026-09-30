import { Link } from "@tanstack/react-router";
import { CaretRight } from "@phosphor-icons/react";
import { Badge, cn } from "@equiped/ui";
import type { AttentionItem, HomeEvaluationItem } from "../types";
import { formatDateTime, getEvaluationStatusBadge } from "../utils/homeData";
import { FacultyWorkflowSignal } from "./FacultyWorkflowSignal";

export interface LedgerEvaluationsTableProps {
  evaluations: HomeEvaluationItem[];
  isFiltered?: boolean;
}

export function LedgerEvaluationsTable({
  evaluations,
  isFiltered = false,
}: LedgerEvaluationsTableProps) {
  return (
    <table className="w-full min-w-[40rem] border-collapse text-left">
      <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
        <tr>
          <th
            scope="col"
            className="pl-4 sm:pl-6 pr-4 py-3 w-full min-w-[14rem] text-left"
          >
            Module
          </th>
          <th scope="col" className="whitespace-nowrap px-4 py-3 text-left">
            Status
          </th>
          <th scope="col" className="whitespace-nowrap px-4 py-3 text-left">
            Submitted
          </th>
          <th scope="col" className="pl-4 pr-4 sm:pr-6 py-3 text-right">
            Action
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border bg-surface text-sm text-text">
        {evaluations.length === 0 ? (
          <tr>
            <td
              colSpan={4}
              className="px-6 py-10 text-center text-sm text-text-muted"
            >
              {isFiltered ? (
                <p>
                  No matching evaluations. Try a different title or evaluation
                  ID.
                </p>
              ) : (
                <FacultyWorkflowSignal
                  title="No evaluations on record"
                  description="Your evaluation results will appear here."
                />
              )}
            </td>
          </tr>
        ) : (
          evaluations.map((ev) => {
            const evalBadge = getEvaluationStatusBadge(ev.status);
            return (
              <tr
                key={ev.evaluation_id}
                className="transition-colors hover:bg-surface-subtle/50 focus-within:bg-surface-subtle/50"
              >
                <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                  <div className="space-y-1">
                    <span className="block break-words text-sm font-medium leading-snug text-text">
                      {ev.document_title || "Untitled SLM"}
                    </span>
                    <span className="block break-all font-mono text-xs tabular-nums text-text-muted">
                      {ev.evaluation_id}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <span
                    className={cn(
                      "inline-flex items-center whitespace-nowrap rounded-xs px-2 py-0.5 text-xs font-medium",
                      evalBadge.className,
                    )}
                  >
                    {evalBadge.label}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-[13px] leading-relaxed tabular-nums text-text-muted">
                  <span className="block min-w-28">
                    {formatDateTime(ev.submitted_at)}
                  </span>
                </td>
                <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                  <Link
                    to="/evaluations/$id"
                    params={{ id: ev.evaluation_id }}
                    className="inline-flex min-h-10 items-center gap-1 whitespace-nowrap rounded-sm text-sm font-medium text-primary transition-colors hover:text-primary-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <span>
                      View details
                      <span className="sr-only">
                        {" "}
                        for {ev.document_title || "Untitled SLM"}
                      </span>
                    </span>
                    <CaretRight className="size-4" aria-hidden="true" />
                  </Link>
                </td>
              </tr>
            );
          })
        )}
      </tbody>
    </table>
  );
}

export interface LedgerAttentionTableProps {
  issues: AttentionItem[];
  isFiltered?: boolean;
}

export function LedgerAttentionTable({
  issues,
  isFiltered = false,
}: LedgerAttentionTableProps) {
  return (
    <table className="w-full min-w-[40rem] border-collapse text-left">
      <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
        <tr>
          <th
            scope="col"
            className="pl-4 sm:pl-6 pr-4 py-3 w-full min-w-[14rem] text-left"
          >
            Module
          </th>
          <th scope="col" className="whitespace-nowrap px-4 py-3 text-left">
            Attention reason
          </th>
          <th scope="col" className="pl-4 pr-4 sm:pr-6 py-3 text-right">
            Action
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border bg-surface text-sm text-text">
        {issues.length === 0 ? (
          <tr>
            <td
              colSpan={3}
              className="px-6 py-10 text-center text-sm text-text-muted"
            >
              {isFiltered ? (
                <p>No matching review items. Try a different search.</p>
              ) : (
                <FacultyWorkflowSignal
                  title="No action items"
                  description="No processing or evaluation issues to review."
                />
              )}
            </td>
          </tr>
        ) : (
          issues.map((issue) => (
            <tr
              key={issue.id}
              className="transition-colors hover:bg-surface-subtle/50 focus-within:bg-surface-subtle/50"
            >
              <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                <span className="break-words font-medium text-text">
                  {issue.title}
                </span>
                <span className="mt-1 block break-words text-sm leading-relaxed text-text-muted">
                  {issue.detail}
                </span>
              </td>
              <td className="px-4 py-3.5">
                <Badge
                  variant="warning"
                  className="whitespace-nowrap font-medium tracking-normal"
                >
                  {issue.type === "document_failed"
                    ? "Processing issue"
                    : "Evaluation issue"}
                </Badge>
              </td>
              <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                <Link
                  to={issue.targetUrl}
                  className="inline-flex min-h-10 items-center gap-1 whitespace-nowrap rounded-sm text-sm font-medium text-primary transition-colors hover:text-primary-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <span>
                    {issue.actionLabel}
                    <span className="sr-only"> for {issue.title}</span>
                  </span>
                  <CaretRight className="size-4" aria-hidden="true" />
                </Link>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
