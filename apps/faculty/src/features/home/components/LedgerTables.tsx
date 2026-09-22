import { Link } from "@tanstack/react-router";
import { CaretRight } from "@phosphor-icons/react";
import { Badge, cn } from "@equiped/ui";
import type { AttentionItem, HomeEvaluationItem } from "../types";
import { formatDateTime, getEvaluationStatusBadge } from "../utils/homeData";
import { FacultyWorkflowSignal } from "./FacultyWorkflowSignal";

export interface LedgerEvaluationsTableProps {
  evaluations: HomeEvaluationItem[];
  isError?: boolean;
}

export function LedgerEvaluationsTable({
  evaluations,
  isError = false,
}: LedgerEvaluationsTableProps) {
  return (
    <table className="w-full text-left border-collapse">
      <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
        <tr>
          <th
            scope="col"
            className="pl-4 sm:pl-6 pr-4 py-3 min-w-[18rem] text-left"
          >
            Document / Evaluation ID
          </th>
          <th scope="col" className="px-4 py-3 text-left">
            Status
          </th>
          <th scope="col" className="px-4 py-3 text-left">
            Submitted
          </th>
          <th scope="col" className="pl-4 pr-4 sm:pr-6 py-3 text-right">
            Action
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border bg-surface text-sm text-text">
        {isError ? (
          <tr>
            <td
              colSpan={4}
              className="px-6 py-12 text-center text-sm text-destructive"
            >
              Unable to load evaluation activity.
            </td>
          </tr>
        ) : evaluations.length === 0 ? (
          <tr>
            <td
              colSpan={4}
              className="px-6 py-10 text-center text-sm text-text-muted"
            >
              <FacultyWorkflowSignal
                title="No evaluations on record"
                description="Once a module moves through review, its scorecard and decision trail will appear here."
              />
            </td>
          </tr>
        ) : (
          evaluations.map((ev) => {
            const evalBadge = getEvaluationStatusBadge(ev.status);
            return (
              <tr
                key={ev.evaluation_id}
                className="transition-colors hover:bg-surface-subtle/70"
              >
                <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                  <div className="space-y-0.5">
                    <span className="text-sm font-semibold text-text block leading-snug">
                      {ev.document_title || "Untitled SLM"}
                    </span>
                    <span className="text-[11px] font-mono text-text-muted block tabular-nums">
                      {ev.evaluation_id}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-xs px-2.5 py-0.5 text-xs font-semibold select-none",
                      evalBadge.className,
                    )}
                  >
                    {evalBadge.label}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-xs text-text-muted tabular-nums">
                  {formatDateTime(ev.submitted_at)}
                </td>
                <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                  <Link
                    to="/evaluations/$id"
                    params={{ id: ev.evaluation_id }}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-strong hover:underline transition-colors"
                  >
                    <span>View Scorecard</span>
                    <CaretRight className="size-3" aria-hidden="true" />
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
}

export function LedgerAttentionTable({ issues }: LedgerAttentionTableProps) {
  return (
    <table className="w-full text-left border-collapse">
      <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
        <tr>
          <th
            scope="col"
            className="pl-4 sm:pl-6 pr-4 py-3 min-w-[18rem] text-left"
          >
            Module
          </th>
          <th scope="col" className="px-4 py-3 text-left">
            Attention Reason
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
              <FacultyWorkflowSignal
                title="No action items"
                description="All modules are processed and evaluated without active errors."
              />
            </td>
          </tr>
        ) : (
          issues.map((issue) => (
            <tr
              key={issue.id}
              className="transition-colors hover:bg-surface-subtle/70"
            >
              <td className="pl-4 sm:pl-6 pr-4 py-3.5">
                <span className="font-semibold text-text">
                  {issue.title}
                </span>
                <span className="text-xs text-text-muted mt-0.5 block">
                  {issue.detail}
                </span>
              </td>
              <td className="px-4 py-3.5">
                <Badge variant="warning" withDot>
                  {issue.type === "document_failed"
                    ? "Processing Issue"
                    : "Evaluation Issue"}
                </Badge>
              </td>
              <td className="pl-4 pr-4 sm:pr-6 py-3.5 text-right">
                <Link
                  to={issue.targetUrl}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-strong hover:underline transition-colors"
                >
                  <span>{issue.actionLabel}</span>
                  <CaretRight className="size-3" aria-hidden="true" />
                </Link>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
