import { useState, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  ChartBar,
  CheckCircle,
  FileText,
  GraduationCap,
  Lightbulb,
  ListChecks,
  Plus,
  ShieldCheck,
  Target,
} from "@phosphor-icons/react";
import { BUTTON_STYLES, cn } from "@equiped/ui";
import type { TargetAgent, TargetAgentMeta } from "@equiped/types";
import type { DeskQueueItem } from "../types";
import { SelectModuleModal } from "./SelectModuleModal";

import { formatDateWithFallback } from "../utils/dateFormatting";

const ROLE_ICONS: Record<TargetAgent, typeof GraduationCap> = {
  sme: GraduationCap,
  coordinator: ListChecks,
  gad: ShieldCheck,
  itso: Lightbulb,
};

export interface SpecialistDirectoryViewProps {
  meta: TargetAgentMeta;
  validAgent: string;
  items: DeskQueueItem[];
}

export function SpecialistDirectoryView({
  meta,
  validAgent,
  items,
}: SpecialistDirectoryViewProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const activeItems = useMemo(() => {
    return items.filter(
      (item) => item.my_status && item.my_status.toUpperCase() === "EVALUATING",
    );
  }, [items]);

  const unevaluatedItems = useMemo(() => {
    return items.filter(
      (item) =>
        !item.my_status ||
        ["PENDING", "READY", "FAILED"].includes(item.my_status.toUpperCase()),
    );
  }, [items]);

  const hasUnevaluated = unevaluatedItems.length > 0;
  const RoleIcon =
    validAgent in ROLE_ICONS
      ? ROLE_ICONS[validAgent as TargetAgent]
      : GraduationCap;

  return (
    <div className="w-full space-y-4">
      {activeItems.length > 0 && (
        <section
          className="border-y border-warning/30 bg-warning-soft/45 px-4 py-3 sm:px-5"
          aria-label="Active evaluations"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-xs font-semibold text-text">
              <span
                className="size-2 rounded-full bg-warning animate-pulse"
                aria-hidden="true"
              />
              Currently evaluating ({activeItems.length})
            </h2>
            <span className="text-[11px] text-text-muted">
              Usually 20–30 seconds
            </span>
          </div>
          <div className="mt-2 divide-y divide-warning/20">
            {activeItems.map((compItem) => (
              <div
                key={compItem.document_id}
                className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-text">
                    {compItem.title}
                  </p>
                  <p className="mt-0.5 text-xs text-text-muted">
                    {[
                      compItem.course_code,
                      compItem.program,
                      `Added ${formatDateWithFallback(compItem.uploaded_at, "Recent")}`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <Link
                  to="/specialists/$agentId/$documentId"
                  params={{
                    agentId: validAgent,
                    documentId: compItem.document_id,
                  }}
                  className={cn(
                    BUTTON_STYLES.base,
                    BUTTON_STYLES.variants.secondary,
                    BUTTON_STYLES.sizes.sm,
                    "w-fit shrink-0 border border-border bg-surface text-xs font-semibold hover:bg-surface-subtle",
                  )}
                >
                  <span>View progress</span>
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      <div
        className="min-h-[calc(100vh-14rem)] overflow-hidden rounded-md border border-border bg-surface"
        role="region"
        aria-label="Evaluation desk workstation"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-sm border border-primary/25 bg-primary-soft text-primary">
              <RoleIcon className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-text-muted">
                Specialist workspace
              </p>
              <h2 className="truncate text-base font-semibold text-text">
                {meta.fullName}
              </h2>
            </div>
          </div>
          <span className="text-xs font-medium text-text-muted">
            {hasUnevaluated
              ? `${unevaluatedItems.length} ready for review`
              : "All modules reviewed"}
          </span>
        </div>

        <div className="grid min-h-[calc(100vh-18rem)] min-w-0 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <div className="flex min-w-0 flex-col px-5 py-8 sm:px-8 sm:py-10">
            {hasUnevaluated ? (
              <div className="max-w-2xl">
                <p className="text-xs font-semibold text-primary">
                  Next review
                </p>
                <h3 className="mt-2 max-w-xl text-xl font-semibold leading-tight text-text sm:text-2xl">
                  Choose a module to begin the {meta.shortLabel} review.
                </h3>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-muted">
                  Select an unevaluated SLM from storage. The automated review
                  will use this desk&apos;s rubric and keep the evidence
                  available for human confirmation.
                </p>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(true)}
                  aria-label="Start New Evaluation"
                  className={cn(
                    BUTTON_STYLES.base,
                    BUTTON_STYLES.variants.primary,
                    BUTTON_STYLES.sizes.md,
                    "mt-6 gap-2 rounded-sm px-5 text-sm font-semibold shadow-xs transition-all hover:shadow active:scale-[0.99]",
                  )}
                >
                  <Plus className="size-4" weight="bold" aria-hidden="true" />
                  <span>Select module</span>
                </button>

                <div
                  className="mt-9 flex flex-wrap items-center gap-x-3 gap-y-2 text-[11px] font-medium text-text-muted"
                  aria-label="Evaluation workflow"
                >
                  {[
                    ["01", "Select module"],
                    ["02", "Run review"],
                    ["03", "Confirm result"],
                  ].map(([step, label], index) => (
                    <div key={step} className="flex items-center gap-2">
                      <span className="flex size-6 items-center justify-center rounded-sm border border-border-strong bg-surface-subtle font-mono text-[10px] text-text">
                        {step}
                      </span>
                      <span>{label}</span>
                      {index < 2 ? (
                        <span
                          className="mx-1 h-px w-6 bg-border-strong"
                          aria-hidden="true"
                        />
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex min-h-64 max-w-xl flex-col justify-center">
                <div className="flex size-11 items-center justify-center rounded-sm border border-success/25 bg-success-soft text-success">
                  <CheckCircle
                    className="size-6"
                    weight="bold"
                    aria-hidden="true"
                  />
                </div>
                <h3 className="mt-5 text-xl font-semibold text-text">
                  No modules awaiting review
                </h3>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-text-muted">
                  Every module currently in storage has been evaluated by the{" "}
                  {meta.shortLabel} desk. New uploads will appear here when they
                  are ready.
                </p>
                <div className="mt-8 flex items-center gap-2 text-xs font-medium text-text-muted">
                  <span
                    className="size-2 rounded-full bg-success"
                    aria-hidden="true"
                  />
                  Desk queue is clear
                </div>
              </div>
            )}

            <div
              className="mt-auto max-w-2xl border-t border-border pt-7"
              aria-label="Queue snapshot"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-text">
                  <ChartBar
                    className="size-4 text-primary"
                    aria-hidden="true"
                  />
                  Queue snapshot
                </div>
                <span className="font-mono text-[11px] text-text-muted">
                  {hasUnevaluated
                    ? `${unevaluatedItems.length} awaiting`
                    : "0 awaiting"}
                </span>
              </div>
              <div
                className="mt-4 grid gap-2 sm:grid-cols-3"
                aria-hidden="true"
              >
                <div className="rounded-sm border border-border bg-surface-subtle/45 p-3">
                  <div className="flex items-center gap-2 text-text-muted">
                    <FileText className="size-3.5" />
                    <span className="text-[11px]">Stored</span>
                  </div>
                  <p className="mt-2 text-lg font-semibold tabular-nums text-text">
                    {items.length}
                  </p>
                  <div className="mt-2 h-1 rounded-full bg-border">
                    <span className="block h-1 w-full rounded-full bg-primary/45" />
                  </div>
                </div>
                <div className="rounded-sm border border-border bg-surface-subtle/45 p-3">
                  <div className="flex items-center gap-2 text-text-muted">
                    <span className="size-3.5 rounded-full border border-warning/60" />
                    <span className="text-[11px]">Awaiting</span>
                  </div>
                  <p className="mt-2 text-lg font-semibold tabular-nums text-text">
                    {unevaluatedItems.length}
                  </p>
                  <div className="mt-2 h-1 rounded-full bg-border">
                    <span
                      className={cn(
                        "block h-1 rounded-full bg-warning/70",
                        unevaluatedItems.length > 0 ? "w-1/2" : "w-0",
                      )}
                    />
                  </div>
                </div>
                <div className="rounded-sm border border-border bg-surface-subtle/45 p-3">
                  <div className="flex items-center gap-2 text-text-muted">
                    <CheckCircle className="size-3.5 text-success" />
                    <span className="text-[11px]">Reviewed here</span>
                  </div>
                  <p className="mt-2 text-lg font-semibold tabular-nums text-text">
                    {
                      items.filter(
                        (item) => item.my_status?.toUpperCase() === "COMPLETED",
                      ).length
                    }
                  </p>
                  <div className="mt-2 h-1 rounded-full bg-border">
                    <span className="block h-1 w-full rounded-full bg-success/60" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <aside
            className="border-t border-border bg-surface-subtle/45 px-5 py-6 sm:px-6 xl:border-l xl:border-t-0"
            aria-label="Review brief"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-text">
              <Target className="size-4 text-primary" aria-hidden="true" />
              Review brief
            </div>
            <p className="mt-2 text-xs leading-relaxed text-text-muted">
              {meta.requirement}
            </p>
            <dl className="mt-6 divide-y divide-border/80 border-y border-border/80 text-xs">
              <div className="py-3">
                <dt className="text-text-muted">Reference policy</dt>
                <dd className="mt-1 font-medium text-text">
                  {meta.requiresCurriculum
                    ? "Verified curriculum required"
                    : "SLM text only"}
                </dd>
              </div>
              <div className="py-3">
                <dt className="text-text-muted">Scoring standard</dt>
                <dd className="mt-1 font-medium text-text">
                  1.00–4.00 adjectival scale
                </dd>
              </div>
              <div className="py-3">
                <dt className="text-text-muted">Review authority</dt>
                <dd className="mt-1 font-medium text-text">
                  Human confirmation required
                </dd>
              </div>
            </dl>
          </aside>
        </div>
      </div>

      {/* ── Selection Modal ── */}
      {isModalOpen && (
        <SelectModuleModal
          agentId={validAgent}
          items={items}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </div>
  );
}
