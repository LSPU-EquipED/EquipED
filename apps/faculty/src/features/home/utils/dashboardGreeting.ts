const dateFormatter = new Intl.DateTimeFormat("en-PH", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
});

export function formatDashboardGreeting(
  now: Date,
  displayName?: string | null,
) {
  const hour = now.getHours();
  const salutation =
    hour < 5
      ? "Welcome back"
      : hour < 12
        ? "Good morning"
        : hour < 18
          ? "Good afternoon"
          : "Good evening";
  const firstName = displayName?.trim().split(/\s+/)[0];

  return {
    greeting: `${salutation}${firstName ? `, ${firstName}` : ""}.`,
    dateLabel: dateFormatter.format(now),
    dateTime: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`,
  };
}
