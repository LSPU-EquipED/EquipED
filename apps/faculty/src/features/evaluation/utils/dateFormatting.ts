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

/** Includes time to distinguish multiple evaluation runs on the same day. */
export function formatEvaluationDateTime(value?: string | null): string {
  if (!value || Number.isNaN(new Date(value).getTime())) return 'Not recorded';
  return new Date(value).toLocaleString('en-PH', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}
