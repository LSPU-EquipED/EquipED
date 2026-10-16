import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "@phosphor-icons/react";
import { Skeleton } from "@equiped/ui";
import type { DocumentStats } from "@equiped/types";
import moduleFolio from "../../../assets/illustrations/module-folio.svg";

export function FacultyModuleOverview({
  stats,
  isLoading,
}: {
  stats: DocumentStats;
  isLoading: boolean;
}) {
  return (
    <section
      className="dashboard-library dashboard-panel"
      aria-labelledby="dashboard-library-heading"
    >
      <div className="flex items-center justify-between gap-3">
        <h2
          id="dashboard-library-heading"
          className="text-base font-semibold text-text"
        >
          Module library
        </h2>
        <Link
          to="/documents"
          aria-label="Open module library"
          className="dashboard-link -mr-2 inline-flex size-10 items-center justify-center rounded-sm text-primary hover:bg-primary-soft"
        >
          <ArrowUpRight size={20} aria-hidden="true" />
        </Link>
      </div>
      <dl aria-label="Module overview" aria-busy={isLoading}>
        <div className="my-3 flex items-center justify-between gap-4">
          <div className="flex flex-col-reverse gap-1">
            <dt className="text-sm text-text-muted">Total modules</dt>
            <dd className="text-3xl font-semibold tabular-nums text-text">
              {isLoading ? (
                <Skeleton className="h-9 w-10" />
              ) : (
                stats.total.toLocaleString()
              )}
            </dd>
          </div>
          <img
            src={moduleFolio}
            alt=""
            width={80}
            height={80}
            className="size-16"
          />
        </div>
        <div className="dashboard-library-counts">
          {[
            { label: "Processed", value: stats.ready, tone: "text-text" },
            { label: "Processing", value: stats.processing, tone: "text-text" },
            {
              label: "Failed uploads",
              value: stats.failed,
              tone: stats.failed > 0 ? "text-destructive" : "text-text",
            },
          ].map(({ label, value, tone }) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs leading-relaxed text-text-muted">
                {label}
              </dt>
              <dd className={`mt-1 text-lg font-medium tabular-nums ${tone}`}>
                {isLoading ? (
                  <Skeleton className="h-6 w-6" />
                ) : (
                  value.toLocaleString()
                )}
              </dd>
            </div>
          ))}
        </div>
      </dl>
    </section>
  );
}
