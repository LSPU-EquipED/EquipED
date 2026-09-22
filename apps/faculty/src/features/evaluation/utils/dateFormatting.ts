export function formatDateWithFallback(
  dateString?: string | null,
  fallback = "Not recorded",
): string {
  if (!dateString) return fallback;
  try {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return fallback;
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return fallback;
  }
}
