import { useDashboardGreeting } from "../hooks/useDashboardGreeting";
import welcomeFolds from "../assets/welcome/welcome-folds.svg";

export function FacultyWelcomeBanner({
  displayName,
}: {
  displayName?: string | null;
}) {
  const { greeting, dateLabel, dateTime } = useDashboardGreeting(displayName);

  return (
    <header className="dashboard-welcome dashboard-panel">
      <img src={welcomeFolds} alt="" className="dashboard-art" />
      <div className="dashboard-greeting">
        <time dateTime={dateTime} className="text-sm text-text-muted">
          {dateLabel}
        </time>
        <h1 className="mt-3 text-2xl font-semibold leading-snug text-text sm:text-3xl">
          {greeting}
        </h1>
        <p className="mt-3 max-w-xs text-sm leading-relaxed text-text-muted">
          Your learning materials, ready for a closer look.
        </p>
      </div>
    </header>
  );
}
