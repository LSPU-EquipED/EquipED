import {
  ArrowRight,
  GraduationCap,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  UsersThree,
} from "@phosphor-icons/react";
import type { TargetAgent } from "@equiped/types";

interface EvaluationProgressVisualProps {
  specialistLabel: string;
  targetAgent?: TargetAgent | "all";
  isActive: boolean;
}

const SPECIALIST_ICONS = {
  sme: GraduationCap,
  coordinator: ListChecks,
  gad: ShieldCheck,
  itso: Lightbulb,
};

export function EvaluationProgressVisual({
  specialistLabel,
  targetAgent,
  isActive,
}: EvaluationProgressVisualProps) {
  const SpecialistIcon =
    targetAgent && targetAgent !== "all"
      ? SPECIALIST_ICONS[targetAgent]
      : UsersThree;
  return (
    <figure
      aria-label={`Module → ${specialistLabel} → Findings`}
      className="mx-auto mb-6 w-full max-w-xl"
    >
      <div
        aria-hidden="true"
        className="grid grid-cols-[minmax(0,1fr)_1rem_minmax(0,1.25fr)_1rem_minmax(0,1fr)] items-center gap-x-2 gap-y-2 sm:grid-cols-[5rem_minmax(1rem,1fr)_7rem_minmax(1rem,1fr)_5rem] sm:gap-x-3"
      >
        <div className="flex h-24 items-center justify-center text-text-muted">
          <svg viewBox="0 0 72 88" fill="none" className="h-20 w-16">
            <path
              d="M12 9H49L63 23V79H12V9Z"
              className="fill-surface-subtle stroke-border-strong"
              strokeWidth="1.5"
            />
            <path
              d="M7 4H44L58 18V74H7V4Z"
              className="fill-surface stroke-border-strong"
              strokeWidth="1.5"
            />
            <path
              d="M44 4V18H58"
              className="stroke-border-strong"
              strokeWidth="1.5"
            />
            <text
              x="17"
              y="39"
              fill="currentColor"
              fontSize="13"
              fontWeight="600"
            >
              SLM
            </text>
            <path
              d="M17 49H46M17 56H46M17 63H34"
              className="stroke-border-strong"
              strokeWidth="1.5"
            />
          </svg>
        </div>
        <div className="flex items-center text-primary/60">
          <span className="h-px flex-1 bg-primary/30" />
          <ArrowRight className="size-4 shrink-0" />
        </div>
        <div className="flex h-24 items-center justify-center">
          <div className="relative flex size-20 items-center justify-center rounded-md border border-primary/25 bg-primary-soft">
            <SpecialistIcon className="size-10 text-primary" weight="duotone" />
            {isActive && (
              <span className="absolute -bottom-1 -right-1 flex size-4 items-center justify-center rounded-full border-2 border-surface bg-primary-soft">
                <span className="size-1.5 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center text-border-strong">
          <span className="h-px flex-1 border-t border-dashed border-border-strong" />
          <ArrowRight className="size-4 shrink-0" />
        </div>
        <div className="flex h-24 items-center justify-center">
          <svg viewBox="0 0 72 88" fill="none" className="h-20 w-16">
            <rect
              x="9"
              y="7"
              width="54"
              height="72"
              rx="3"
              className="fill-surface stroke-border"
              strokeWidth="1.5"
            />
            <path
              d="M19 21H44"
              className="stroke-border-strong"
              strokeWidth="2"
            />
            {[34, 48, 62].map((y) => (
              <g key={y}>
                <rect
                  x="19"
                  y={y}
                  width="6"
                  height="6"
                  rx="1"
                  className="stroke-border-strong"
                />
                <path
                  d={`M32 ${y + 3}H52`}
                  className="stroke-border"
                  strokeWidth="1.5"
                />
              </g>
            ))}
          </svg>
        </div>
        <p className="self-start text-center text-sm text-text-muted">Module</p>
        <span />
        <p className="self-start text-center text-sm font-medium text-primary">
          {specialistLabel}
        </p>
        <span />
        <p className="self-start text-center text-sm text-text-muted">
          Findings
        </p>
      </div>
    </figure>
  );
}
