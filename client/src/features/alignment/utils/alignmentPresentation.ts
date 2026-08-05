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
    border: 'border-[#3b963e]/40',
    background: 'bg-[#3b963e]/5',
    accent: 'text-[#246b29]',
    badge: 'border-[#3b963e]/40 bg-[#3b963e]/10 text-[#246b29]',
  },
  PARTIALLY_MEETS: {
    border: 'border-[#b7791f]/40',
    background: 'bg-[#f2c811]/10',
    accent: 'text-[#8a5a12]',
    badge: 'border-[#b7791f]/40 bg-[#f2c811]/15 text-[#74470a]',
  },
  DOES_NOT_MEET: {
    border: 'border-[#b91c1c]/35',
    background: 'bg-[#b91c1c]/5',
    accent: 'text-[#b91c1c]',
    badge: 'border-[#b91c1c]/35 bg-[#b91c1c]/10 text-[#991b1b]',
  },
  UNAVAILABLE: {
    border: 'border-slate-400',
    background: 'bg-slate-100',
    accent: 'text-slate-700',
    badge: 'border-slate-400 bg-slate-100 text-slate-700',
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
