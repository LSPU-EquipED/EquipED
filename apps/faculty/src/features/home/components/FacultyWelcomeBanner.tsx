import { useDashboardGreeting } from "../hooks/useDashboardGreeting";
import { DashboardWelcomeVisual } from "./DashboardWelcomeVisual";

export function FacultyWelcomeBanner({
  displayName,
}: {
  displayName?: string | null;
}) {
  const { greeting, dateLabel, dateTime } = useDashboardGreeting(displayName);

  return (
    <header className="flex h-full items-center justify-between gap-6 bg-primary-soft/50 px-5 py-6 sm:px-8">
      <div className="min-w-0">
        <time dateTime={dateTime} className="text-sm text-text-muted">
          {dateLabel}
        </time>
        <h1 className="mt-2 break-words text-2xl font-semibold leading-snug text-text sm:text-3xl">
          {greeting}
        </h1>
      </div>
      <div className="hidden w-64 shrink-0 lg:block">
        <DashboardWelcomeVisual />
      </div>
    </header>
  );
}
