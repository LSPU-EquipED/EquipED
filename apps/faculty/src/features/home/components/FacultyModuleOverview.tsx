import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "@phosphor-icons/react";
import { Skeleton } from "@equiped/ui";
import type { DocumentStats } from "@equiped/types";
import moduleCollection from "../../../assets/illustrations/module-collection.svg";

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
      <div className="dashboard-library-content">
        <dl aria-label="Module overview" aria-busy={isLoading}>
          <div className="flex flex-col-reverse gap-1.5">
            <dt className="text-sm text-text-muted">Total modules</dt>
            <dd className="text-3xl font-semibold tabular-nums text-text">
              {isLoading ? (
                <Skeleton className="h-9 w-10" />
              ) : (
                stats.total.toLocaleString()
              )}
            </dd>
          </div>
        </dl>
        <img
          src={moduleCollection}
          alt=""
          width={320}
          height={220}
          className="dashboard-library-illustration"
        />
      </div>
      {!isLoading && (stats.processing > 0 || stats.failed > 0) && (
        <p
          aria-label="Module processing updates"
          className="flex flex-wrap gap-x-4 gap-y-1 text-sm tabular-nums"
        >
          {stats.processing > 0 && (
            <span className="text-text-muted">
              {stats.processing.toLocaleString()} processing
            </span>
          )}
          {stats.failed > 0 && (
            <span className="text-destructive">
              {stats.failed.toLocaleString()}{" "}
              {stats.failed === 1 ? "failed upload" : "failed uploads"}
            </span>
          )}
        </p>
      )}
    </section>
  );
}
