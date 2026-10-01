import { getErrorMessage } from "@equiped/api-client";
import { Button } from "@equiped/ui";
import { useFacultyHome } from "../hooks/useFacultyHome";
import { FacultyActiveEvaluationBanner } from "./FacultyActiveEvaluationBanner";
import { FacultyOperationalLedger } from "./FacultyOperationalLedger";
import { FacultyQuickActions } from "./FacultyQuickActions";
import type { FacultyWorkspaceAccess } from "../types";
import { FacultyPulseStrip } from "./FacultyPulseStrip";
import { FacultyWelcomeBanner } from "./FacultyWelcomeBanner";

export function FacultyHome({
  displayName,
  evaluatorPermissions,
  userRole,
}: FacultyWorkspaceAccess & { displayName?: string | null } = {}) {
  const { isLoading, isError, error, stats, homeData, evaluations, refetch } =
    useFacultyHome();

  const hasActiveEvaluation = !isError && Boolean(homeData.activeEvaluation);

  return (
    <section className="mx-auto max-w-[108rem] space-y-5 px-4 py-6 sm:px-7 sm:py-8">
      <div className="min-w-0 overflow-hidden rounded-md border border-border bg-surface">
        <FacultyWelcomeBanner displayName={displayName} />
      </div>
      {!isError && <FacultyPulseStrip stats={stats} isLoading={isLoading} />}

      {isError ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-destructive bg-destructive-soft p-4 text-sm text-destructive"
        >
          <span>
            {getErrorMessage(error, "Unable to load workspace data.")}
          </span>
          <Button variant="secondary" size="sm" onClick={refetch}>
            Retry
          </Button>
        </div>
      ) : null}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_clamp(18rem,23vw,22rem)] min-[85rem]:gap-x-7">
        <div className="relative min-w-0 space-y-5 xl:col-start-2 xl:row-start-1 xl:before:pointer-events-none xl:before:absolute xl:before:inset-y-0 xl:before:-left-2.5 xl:before:border-l xl:before:border-border min-[85rem]:before:-left-3.5">
          {hasActiveEvaluation && (
            <FacultyActiveEvaluationBanner
              evaluation={homeData.activeEvaluation}
            />
          )}
          <FacultyQuickActions
            evaluatorPermissions={evaluatorPermissions}
            userRole={userRole}
          />
        </div>
        <div className="min-w-0 xl:col-start-1 xl:row-start-1">
          <FacultyOperationalLedger
            evaluations={evaluations}
            recentIssues={homeData.recentIssues}
            isLoading={isLoading}
            isError={isError}
            onRefresh={refetch}
          />
        </div>
      </div>
    </section>
  );
}
