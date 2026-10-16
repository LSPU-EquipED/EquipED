import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "@phosphor-icons/react";
import type { TargetAgent } from "@equiped/types";
import type { FacultyWorkspaceAccess } from "../types";
import contentReview from "../../../assets/illustrations/specialists/content-review.svg";
import curriculumReview from "../../../assets/illustrations/specialists/curriculum-review.svg";
import inclusiveReview from "../../../assets/illustrations/specialists/inclusive-review.svg";
import innovationReview from "../../../assets/illustrations/specialists/innovation-review.svg";

const workspaces: {
  id: TargetAgent;
  label: string;
  description: string;
  artwork: string;
}[] = [
  {
    id: "sme",
    label: "Subject Matter Expert",
    description: "Content accuracy and mastery",
    artwork: contentReview,
  },
  {
    id: "coordinator",
    label: "Program Coordinator",
    description: "Curriculum & degree compliance",
    artwork: curriculumReview,
  },
  {
    id: "gad",
    label: "Gender and Development",
    description: "Inclusivity and representation",
    artwork: inclusiveReview,
  },
  {
    id: "itso",
    label: "ITSO",
    description: "Intellectual property and citations",
    artwork: innovationReview,
  },
];

export function FacultyWorkspaces({
  evaluatorPermissions,
  userRole,
}: FacultyWorkspaceAccess) {
  // Match the route guard: absent and empty assignments are unrestricted.
  const allowed = workspaces.filter(
    ({ id }) =>
      userRole === "admin" ||
      !evaluatorPermissions?.length ||
      evaluatorPermissions.includes(id),
  );
  if (!allowed.length) return null;

  return (
    <section
      className="dashboard-evaluations"
      aria-labelledby="dashboard-workspaces-heading"
    >
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="dashboard-workspaces-heading"
          className="text-base font-semibold text-text"
        >
          Evaluation workspaces
        </h2>
        <span className="text-sm text-text-muted">
          Review a module with your assigned specialists
        </span>
      </div>
      <nav
        aria-label="Evaluation workspaces"
        className="dashboard-workspaces"
        data-count={allowed.length}
      >
        {allowed.map(({ id, label, description, artwork }) => (
          <Link
            key={id}
            to="/specialists/$agentId"
            params={{ agentId: id }}
            className="dashboard-workspace dashboard-panel dashboard-link group"
          >
            <img
              src={artwork}
              width={80}
              height={80}
              alt=""
              className="dashboard-workspace-art"
            />
            <div className="dashboard-workspace-copy">
              <h3 className="text-base font-semibold leading-snug text-text group-hover:text-primary">
                {label}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                {description}
              </p>
            </div>
            <ArrowUpRight
              size={19}
              className="dashboard-workspace-arrow text-text-muted group-hover:text-primary"
              aria-hidden="true"
            />
          </Link>
        ))}
      </nav>
    </section>
  );
}
