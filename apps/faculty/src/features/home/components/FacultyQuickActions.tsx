import { useId } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowUpRight,
  BookOpenText,
  GitFork,
  GraduationCap,
  Lightbulb,
  ListChecks,
  ShieldCheck,
} from "@phosphor-icons/react";
import type { TargetAgent } from "@equiped/types";

import type { FacultyWorkspaceAccess } from "../types";

const specialists: {
  id: TargetAgent;
  label: string;
  description: string;
  icon: typeof GraduationCap;
}[] = [
  {
    id: "sme",
    label: "SME Specialist",
    description: "Content accuracy and mastery",
    icon: GraduationCap,
  },
  {
    id: "coordinator",
    label: "Program Coordinator",
    description: "Curriculum & degree compliance",
    icon: ListChecks,
  },
  {
    id: "gad",
    label: "GAD Specialist",
    description: "Inclusivity and representation",
    icon: ShieldCheck,
  },
  {
    id: "itso",
    label: "ITSO Specialist",
    description: "Intellectual property and citations",
    icon: Lightbulb,
  },
];

const alignmentActions = [
  {
    to: "/syllabus-alignment",
    label: "Syllabus alignment",
    icon: BookOpenText,
  },
  { to: "/curriculum-alignment", label: "Curriculum check", icon: GitFork },
] as const;

const actionClassName =
  "group flex min-h-20 items-center gap-3 px-4 py-5 transition-colors duration-150 hover:bg-surface-subtle/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring";
const groupClassName =
  "divide-y divide-border overflow-hidden rounded-md border border-border bg-surface";

function ActionContent({
  icon: Icon,
  label,
  description,
}: {
  icon: typeof GraduationCap;
  label: string;
  description?: string;
}) {
  return (
    <>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-subtle/50 text-text-muted group-hover:border-primary/30 group-hover:text-primary">
        <Icon className="size-4.5" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold leading-5 text-text group-hover:text-primary">
          {label}
        </span>
        {description && (
          <span className="mt-1.5 block text-sm leading-relaxed text-text-muted">
            {description}
          </span>
        )}
      </span>
      <ArrowUpRight
        className="size-4 shrink-0 text-text-muted group-hover:text-primary"
        aria-hidden="true"
      />
    </>
  );
}

export function FacultyQuickActions({
  evaluatorPermissions,
  userRole,
}: FacultyWorkspaceAccess) {
  const id = useId();
  // Matches the route guard: an absent or empty assignment is unrestricted.
  const allowedSpecialists = specialists.filter(
    ({ id }) =>
      userRole === "admin" ||
      !evaluatorPermissions?.length ||
      evaluatorPermissions.includes(id),
  );

  return (
    <nav aria-label="Quick actions" className="min-w-0 space-y-7">
      {allowedSpecialists.length > 0 && (
        <section aria-labelledby={`${id}-evaluations`}>
          <h2
            id={`${id}-evaluations`}
            className="mb-4 text-base font-semibold text-text"
          >
            Evaluation workspaces
          </h2>
          <ul className={groupClassName}>
            {allowedSpecialists.map(({ id, ...content }) => (
              <li key={id}>
                <Link
                  to="/specialists/$agentId"
                  params={{ agentId: id }}
                  className={actionClassName}
                >
                  <ActionContent {...content} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby={`${id}-alignment`}>
        <h2
          id={`${id}-alignment`}
          className="mb-4 text-base font-semibold text-text"
        >
          Alignment checks
        </h2>
        <ul className={groupClassName}>
          {alignmentActions.map(({ to, ...content }) => (
            <li key={to}>
              <Link to={to} className={actionClassName}>
                <ActionContent {...content} />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </nav>
  );
}
