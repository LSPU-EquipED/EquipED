export function getStatusVariant(status: string) {
  const normalizedStatus = status.toUpperCase();
  if (normalizedStatus === 'FAILED' || normalizedStatus === 'ERROR') return 'destructive' as const;
  if (normalizedStatus.startsWith('COMPLETED')) return 'success' as const;
  if (['EVALUATING', 'PREPROCESSING', 'SYNTHESIZING', 'PROCESSING'].includes(normalizedStatus)) return 'info' as const;
  if (['SUBMITTED', 'PENDING', 'QUEUED'].includes(normalizedStatus)) return 'warning' as const;
  return 'neutral' as const;
}

const historyDateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

export function formatDate(value: string): string {
  try {
    return historyDateFormatter.format(new Date(value));
  } catch {
    return '';
  }
}

export function formatDuration(
  seconds?: number | null,
  submittedAt?: string,
  completedAt?: string | null,
): string | null {
  if (typeof seconds === 'number' && seconds > 0) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  }
  if (submittedAt && completedAt) {
    const diffMs = new Date(completedAt).getTime() - new Date(submittedAt).getTime();
    if (diffMs > 0) {
      const totalSecs = Math.round(diffMs / 1000);
      const mins = Math.floor(totalSecs / 60);
      const secs = totalSecs % 60;
      if (mins > 0) return `${mins}m ${secs}s`;
      return `${secs}s`;
    }
  }
  return null;
}

export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffSecs = Math.round((now.getTime() - date.getTime()) / 1000);
    if (Number.isNaN(diffSecs)) return '';
    if (diffSecs < 60) return 'just now';
    const diffMins = Math.round(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    const diffMonths = Math.round(diffDays / 30);
    return `${diffMonths}mo ago`;
  } catch {
    return '';
  }
}
