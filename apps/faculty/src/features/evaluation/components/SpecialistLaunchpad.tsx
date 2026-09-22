import {
  BookOpen,
  CheckCircle,
  ChartBar,
  FileText,
  GraduationCap,
  Lightbulb,
  ListChecks,
  Play,
  ShieldCheck,
} from "@phosphor-icons/react";
import { Badge, BUTTON_STYLES, cn } from "@equiped/ui";
import type {
  ClientDocument,
  TargetAgent,
  TargetAgentMeta,
} from "@equiped/types";
import type { DeskQueueItem } from "../types";

import { formatDateWithFallback } from "../utils/dateFormatting";

const ROLE_ICONS: Record<TargetAgent, typeof GraduationCap> = {
  sme: GraduationCap,
  coordinator: ListChecks,
  gad: ShieldCheck,
  itso: Lightbulb,
};

export interface SpecialistLaunchpadProps {
  activeItem: DeskQueueItem | null;
  activeDocument: ClientDocument | null;
  meta: TargetAgentMeta;
  validAgent: string;
  onLaunch: () => void;
}

export function SpecialistLaunchpad({
  activeItem,
  activeDocument,
  meta,
  validAgent,
  onLaunch,
}: SpecialistLaunchpadProps) {
  const displayTitle =
    activeDocument?.lessonTitle ||
    activeDocument?.courseTitle ||
    activeItem?.title ||
    activeDocument?.title ||
    "Course Module";
  const courseCode = activeItem?.course_code || activeDocument?.courseCode;
  const program = activeItem?.program || activeDocument?.program;
  const uploadDate = formatDateWithFallback(
    activeItem?.uploaded_at || activeDocument?.uploadedAt,
    "Not specified",
  );
  const RoleIcon =
    validAgent in ROLE_ICONS
      ? ROLE_ICONS[validAgent as TargetAgent]
      : GraduationCap;

  const previewRows = [
    {
      label: "Source excerpts",
      detail: "Module text",
      icon: FileText,
      width: "w-[82%]",
    },
    {
      label: "Rubric criteria",
      detail: `${meta.shortLabel} desk`,
      icon: RoleIcon,
      width: "w-[68%]",
    },
    {
      label: "Review record",
      detail: "Scores + findings",
      icon: CheckCircle,
      width: "w-[54%]",
    },
  ];

  return (
    <section
      className="overflow-hidden rounded-md border border-border bg-surface"
      role="region"
      aria-label="Module Evaluation Launchpad"
    >
      <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 p-6 sm:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-sm border border-primary/20 bg-primary-soft text-primary">
              <RoleIcon className="size-4.5" aria-hidden="true" />
            </span>
            <Badge variant="info" className="font-semibold">
              {meta.shortLabel} desk review
            </Badge>
            <Badge variant="neutral" className="font-semibold">
              Unevaluated
            </Badge>
          </div>

          <p className="mt-9 text-xs font-semibold text-primary">
            Selected module
          </p>
          <h1
            className="mt-2 max-w-2xl break-words text-2xl font-semibold leading-tight text-text sm:text-[2rem]"
            title={displayTitle}
          >
            {displayTitle}
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-muted">
            Ready for a focused review against the {meta.shortLabel} rubric.
          </p>

          <dl className="mt-8 grid max-w-2xl grid-cols-2 gap-x-6 gap-y-4 border-y border-border py-5 text-xs sm:grid-cols-3">
            <div>
              <dt className="text-text-muted">Course</dt>
              <dd className="mt-1 font-mono font-semibold text-text">
                {courseCode || "Not specified"}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Program</dt>
              <dd className="mt-1 font-medium text-text">
                {program || "Not specified"}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Uploaded</dt>
              <dd className="mt-1 font-medium text-text">{uploadDate}</dd>
            </div>
          </dl>

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={onLaunch}
              aria-label="Launch review (usually 20 to 30 seconds)"
              className={cn(
                BUTTON_STYLES.base,
                BUTTON_STYLES.variants.primary,
                BUTTON_STYLES.sizes.md,
                "h-10 gap-2.5 rounded-sm px-5 text-xs font-semibold shadow-xs transition-all hover:shadow active:scale-[0.99] cursor-pointer sm:text-sm",
              )}
            >
              <Play
                className="size-4 fill-current"
                weight="fill"
                aria-hidden="true"
              />
              <span>Launch review</span>
            </button>
            <span className="text-xs text-text-muted">
              Usually 20–30 seconds
            </span>
          </div>
        </div>

        <aside
          className="border-t border-border bg-surface-subtle/55 px-6 py-7 sm:px-8 lg:border-l lg:border-t-0 lg:px-7"
          aria-label="Scorecard preview"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold text-text-muted">
                Output preview
              </p>
              <h2 className="mt-1 text-base font-semibold text-text">
                Evidence scorecard
              </h2>
            </div>
            <span className="flex size-8 items-center justify-center rounded-sm border border-primary/20 bg-primary-soft text-primary">
              <ChartBar className="size-4" aria-hidden="true" />
            </span>
          </div>

          <div className="mt-7 space-y-3" aria-hidden="true">
            {previewRows.map((row, index) => {
              const Icon = row.icon;
              return (
                <div
                  key={row.label}
                  className="rounded-sm border border-border bg-surface px-3 py-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-sm bg-primary-soft text-primary">
                      <Icon className="size-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2 text-[11px]">
                        <span className="font-semibold text-text">
                          {row.label}
                        </span>
                        <span className="font-mono text-text-muted">
                          0{index + 1}
                        </span>
                      </div>
                      <div className="mt-2 h-1 rounded-full bg-border">
                        <span
                          className={cn(
                            "block h-1 rounded-full bg-primary/65",
                            row.width,
                          )}
                        />
                      </div>
                    </div>
                  </div>
                  <p className="mt-2 pl-8 text-[11px] text-text-muted">
                    {row.detail}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-6 border-t border-border pt-5" aria-hidden="true">
            <div className="flex items-center justify-between gap-3 text-[11px]">
              <span className="font-semibold text-text">Criteria profile</span>
              <span className="font-mono text-text-muted">1 — 4</span>
            </div>
            <div className="mt-4 flex h-20 items-end gap-2">
              {["h-10", "h-14", "h-7", "h-16"].map((height, index) => (
                <span
                  key={index}
                  className={cn(
                    "block flex-1 rounded-t-sm bg-primary/20",
                    height,
                    index === 3 && "bg-primary/60",
                    index === 1 && "bg-primary/40",
                  )}
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between font-mono text-[10px] text-text-muted">
              <span>1</span>
              <span>2</span>
              <span>3</span>
              <span>4</span>
            </div>
          </div>

          <div className="mt-6 flex items-start gap-2 border-t border-border pt-4 text-xs leading-relaxed text-text-muted">
            <BookOpen
              className="mt-0.5 size-3.5 shrink-0 text-primary"
              aria-hidden="true"
            />
            <span>
              {meta.requiresCurriculum
                ? "Approved syllabus context is included."
                : "The SLM text is reviewed directly."}
            </span>
          </div>
        </aside>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-subtle/35 px-5 py-3.5 text-xs sm:px-6">
        <span className="inline-flex items-center gap-2 text-text-muted">
          <span
            className="size-1.5 rounded-full bg-warning"
            aria-hidden="true"
          />
          Human confirmation required before this result is authoritative.
        </span>
        <span className="font-medium text-text-muted">
          1.00–4.00 scoring scale
        </span>
      </div>
    </section>
  );
}
