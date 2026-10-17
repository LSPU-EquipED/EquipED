import { cn } from "@equiped/ui";
import type { ClientDocument } from "@equiped/types";
import { formatDate, sourceTypeLabels } from "../utils/document.utils";
import { DocumentActionsMenu } from "./DocumentActionsMenu";

interface DocumentTableProps {
  documents: ClientDocument[];
  flashId: string | null;
  onInspect?: (document: ClientDocument) => void;
}

export function DocumentTable({
  documents,
  flashId,
  onInspect,
}: DocumentTableProps) {
  const hasMultipleTypes = documents.some((d) => d.sourceType !== "slm");

  return (
    <div className="overflow-x-auto min-w-0 w-full">
      <table className="w-full sm:min-w-[44rem] table-fixed border-collapse border-spacing-0 text-left">
        <caption className="sr-only">Course module inventory</caption>
        <thead className="border-b border-border bg-surface-subtle text-xs font-medium text-text-muted">
          <tr>
            <th
              scope="col"
              className={cn(
                "py-3 pl-4 pr-3.5 text-left align-middle sm:pl-6",
                hasMultipleTypes
                  ? "sm:w-[40%] sm:min-w-[16rem]"
                  : "sm:w-[44%] sm:min-w-[16rem]",
              )}
            >
              Module
            </th>
            <th
              scope="col"
              className={cn(
                "hidden py-3 px-3.5 text-left align-middle sm:table-cell",
                hasMultipleTypes
                  ? "w-[24%] min-w-[12rem]"
                  : "w-[28%] min-w-[13rem]",
              )}
            >
              Course
            </th>
            <th
              scope="col"
              className="hidden py-3 px-3.5 text-left align-middle sm:table-cell w-28 min-w-[6.5rem]"
            >
              Program
            </th>
            {hasMultipleTypes && (
              <th
                scope="col"
                className="hidden py-3 px-3.5 text-left align-middle sm:table-cell w-28 min-w-[6.5rem]"
              >
                Type
              </th>
            )}
            <th
              scope="col"
              className={cn(
                "hidden py-3 px-3.5 text-left align-middle sm:table-cell",
                hasMultipleTypes ? "w-32 min-w-[7rem]" : "w-32 min-w-[8rem]",
              )}
            >
              Uploaded
            </th>
            <th
              scope="col"
              className="sticky right-0 w-20 bg-surface-subtle py-3 pl-2 pr-4 text-right align-middle"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {documents.map((document) => {
            const isFlashing = flashId === document.documentId;

            return (
              <tr
                key={document.documentId}
                className={cn(isFlashing && "animate-ledger-flash-decay")}
              >
                <td
                  className={cn(
                    "py-3 pl-4 pr-3.5 align-middle sm:pl-6",
                    hasMultipleTypes
                      ? "sm:w-[40%] sm:min-w-[16rem]"
                      : "sm:w-[44%] sm:min-w-[16rem]",
                  )}
                >
                  <span
                    className="block truncate font-semibold text-sm text-text"
                    title={document.title}
                  >
                    {document.title}
                  </span>
                  <p className="mt-1 text-xs leading-relaxed text-text-muted sm:hidden">
                    {[
                      document.courseCode || document.courseTitle,
                      document.program,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    <span className="block tabular-nums">
                      {formatDate(document.uploadedAt)}
                    </span>
                  </p>
                </td>

                <td
                  className={cn(
                    "hidden py-3 px-3.5 align-middle sm:table-cell",
                    hasMultipleTypes
                      ? "w-[24%] min-w-[12rem]"
                      : "w-[28%] min-w-[13rem]",
                  )}
                >
                  <span
                    className="block truncate text-xs sm:text-sm text-text-muted font-medium"
                    title={
                      [document.courseCode, document.courseTitle]
                        .filter(Boolean)
                        .join(" — ") || undefined
                    }
                  >
                    {document.courseCode
                      ? document.courseTitle
                        ? `${document.courseCode} — ${document.courseTitle}`
                        : document.courseCode
                      : (document.courseTitle ?? "Not specified")}
                  </span>
                </td>

                <td className="hidden py-3 px-3.5 align-middle sm:table-cell w-28 min-w-[6.5rem]">
                  {document.program ? (
                    <span className="text-sm text-text-muted">
                      {document.program}
                    </span>
                  ) : (
                    <span className="text-text-muted/60 select-none font-mono text-xs">
                      Not specified
                    </span>
                  )}
                </td>

                {hasMultipleTypes && (
                  <td className="hidden py-3 px-3.5 align-middle sm:table-cell text-xs text-text-muted font-medium whitespace-nowrap w-28 min-w-[6.5rem]">
                    {sourceTypeLabels[document.sourceType]}
                  </td>
                )}

                <td
                  className={cn(
                    "hidden py-3 px-3.5 align-middle sm:table-cell text-xs text-text-muted font-medium whitespace-nowrap tabular-nums",
                    hasMultipleTypes
                      ? "w-32 min-w-[7.5rem]"
                      : "w-36 min-w-[8.5rem]",
                  )}
                >
                  {formatDate(document.uploadedAt)}
                </td>

                <td className="sticky right-0 w-20 bg-surface py-3 pl-2 pr-4 text-right align-middle">
                  <DocumentActionsMenu
                    document={document}
                    onInspect={onInspect}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
