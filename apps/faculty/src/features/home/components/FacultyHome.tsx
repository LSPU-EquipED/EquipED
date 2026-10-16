import { getErrorMessage } from "@equiped/api-client";
import { Button } from "@equiped/ui";
import type { FacultyWorkspaceAccess } from "../types";
import { useFacultyHome } from "../hooks/useFacultyHome";
import { FacultyActiveEvaluationBanner } from "./FacultyActiveEvaluationBanner";
import { FacultyWelcomeBanner } from "./FacultyWelcomeBanner";
import { FacultyWorkspaces } from "./FacultyWorkspaces";
import { FacultyModuleOverview } from "./FacultyModuleOverview";
import { FacultyRecentActivity } from "./FacultyRecentActivity";
import { FacultyAlignmentChecks } from "./FacultyAlignmentChecks";
import "../styles/dashboard.css";

export function FacultyHome({
  displayName,
  ...access
}: FacultyWorkspaceAccess & { displayName?: string | null } = {}) {
  const { stats, evaluations, homeData, isLoading, isError, error, refetch } =
    useFacultyHome();

  return (
    <section className="faculty-dashboard mx-auto max-w-[108rem] px-4 py-6 sm:px-7 sm:py-8">
      <div className="dashboard-bento">
        <FacultyWelcomeBanner displayName={displayName} />
        {!isError && (
          <FacultyModuleOverview stats={stats} isLoading={isLoading} />
        )}
        {isError && (
          <div
            role="alert"
            className="dashboard-notice flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive-soft p-5 text-sm text-destructive"
          >
            <span>
              {getErrorMessage(error, "Unable to load workspace data.")}
            </span>
            <Button variant="secondary" size="sm" onClick={refetch}>
              Retry
            </Button>
          </div>
        )}
        {!isError && homeData.activeEvaluation && (
          <div className="dashboard-progress">
            <FacultyActiveEvaluationBanner
              evaluation={homeData.activeEvaluation}
            />
          </div>
        )}
        <FacultyWorkspaces {...access} />
        {!isError && (
          <FacultyRecentActivity
            evaluations={evaluations}
            isLoading={isLoading}
          />
        )}
        <FacultyAlignmentChecks />
      </div>
    </section>
  );
}
