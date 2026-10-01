import { Skeleton, cn } from "@equiped/ui";
import type { DocumentStats } from "@equiped/types";

export function FacultyPulseStrip({
  stats,
  isLoading,
}: {
  stats: DocumentStats;
  isLoading: boolean;
}) {
  const metrics = [
    { label: "Total modules", value: stats.total },
    { label: "Processed", value: stats.ready },
    { label: "Processing", value: stats.processing },
    {
      label: "Failed uploads",
      value: stats.failed,
      needsAttention: stats.failed > 0,
    },
  ];

  return (
    <dl
      aria-label="Module overview"
      aria-busy={isLoading}
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
    >
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-1 rounded-md border border-border bg-surface px-4 py-3 sm:px-5"
        >
          <dt className="text-sm text-text-muted">{metric.label}</dt>
          <dd
            className={cn(
              "text-xl font-semibold tabular-nums",
              metric.needsAttention ? "text-destructive" : "text-text",
            )}
          >
            {isLoading ? (
              <Skeleton className="h-7 w-8" />
            ) : (
              metric.value.toLocaleString()
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
