import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import { useFacultyHome } from '../hooks/useFacultyHome';
import { FacultyActiveEvaluationBanner } from './FacultyActiveEvaluationBanner';
import { FacultyLaunchpads } from './FacultyLaunchpads';
import { FacultyOperationalLedger } from './FacultyOperationalLedger';
import { FacultyPulseStrip } from './FacultyPulseStrip';

export interface FacultyHomeProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}

export function FacultyHome({ evaluatorPermissions, userRole }: FacultyHomeProps = {}) {
  const { isLoading, isError, error, stats, homeData, evaluations, refetch } = useFacultyHome();
  const evaluationsList = evaluations.length > 0 ? evaluations : homeData.recentEvaluations;

  return (
    <section className="mx-auto max-w-[108rem] space-y-7 px-4 py-6 sm:px-7 sm:py-8">
      <h1 className="sr-only">Faculty workspace overview</h1>

      {isError ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-destructive bg-destructive-soft p-4 text-sm text-destructive">
          <span>{getErrorMessage(error, 'Unable to load workspace data.')}</span>
          <Button variant="secondary" size="sm" onClick={refetch}>Retry</Button>
        </div>
      ) : null}

      {!isError && <FacultyPulseStrip stats={stats} isLoading={isLoading} />}

      <div className="grid min-w-0 gap-8 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0 space-y-7">
          {!isError && <FacultyActiveEvaluationBanner evaluation={homeData.activeEvaluation} />}

          <FacultyOperationalLedger
            evaluations={evaluationsList}
            recentIssues={homeData.recentIssues}
            isLoading={isLoading}
            isError={isError}
          />
        </div>
        <FacultyLaunchpads evaluatorPermissions={evaluatorPermissions} userRole={userRole} />
      </div>
    </section>
  );
}
