import type { AlignmentLevel, AlignmentRun } from '../types';

export const levelLabels: Record<AlignmentLevel, string> = {
  MEETS: 'Meets',
  PARTIALLY_MEETS: 'Partially meets',
  DOES_NOT_MEET: 'Does not meet',
  UNAVAILABLE: 'Unavailable',
};

export const levelStyles: Record<
  AlignmentLevel,
  { border: string; background: string; accent: string; badge: string }
> = {
  MEETS: {
    border: 'border-success/30',
    background: 'bg-success-soft/30',
    accent: 'text-success',
    badge: 'border-success/30 bg-success-soft text-success',
  },
  PARTIALLY_MEETS: {
    border: 'border-warning/30',
    background: 'bg-warning-soft/30',
    accent: 'text-warning',
    badge: 'border-warning/30 bg-warning-soft text-warning',
  },
  DOES_NOT_MEET: {
    border: 'border-destructive/30',
    background: 'bg-destructive-soft/30',
    accent: 'text-destructive',
    badge: 'border-destructive/30 bg-destructive-soft text-destructive',
  },
  UNAVAILABLE: {
    border: 'border-border',
    background: 'bg-surface-subtle',
    accent: 'text-text-muted',
    badge: 'border-border bg-surface-subtle text-text-muted',
  },
};

export function isAlignmentActive(run?: AlignmentRun | null): boolean {
  return run?.status === 'QUEUED' || run?.status === 'RUNNING';
}

export function isAlignmentComplete(run?: AlignmentRun | null): run is AlignmentRun {
  return run?.status === 'COMPLETED' && Boolean(run.alignment_artifact);
}

export function shouldConfirmAlignmentReplacement(run?: AlignmentRun | null): boolean {
  return Boolean(run) && !isAlignmentActive(run);
}
