import { useMemo } from 'react';
import {
  GraduationCap,
  Lightbulb,
  ListChecks,
  ShieldCheck,
} from '@phosphor-icons/react';
import type { TargetAgent } from '@equiped/types';

export interface EvaluatorSpecialist {
  id: TargetAgent;
  label: string;
  short: string;
  desc: string;
  icon: typeof GraduationCap;
}

export const ALL_SPECIALISTS: EvaluatorSpecialist[] = [
  {
    id: 'sme',
    label: 'Subject Matter Expert',
    short: 'SME',
    desc: 'Content accuracy and mastery',
    icon: GraduationCap,
  },
  {
    id: 'coordinator',
    label: 'Program Coordinator',
    short: 'Coordinator',
    desc: 'Curriculum & degree compliance',
    icon: ListChecks,
  },
  {
    id: 'gad',
    label: 'Gender & Development',
    short: 'GAD',
    desc: 'Inclusivity & fair representation',
    icon: ShieldCheck,
  },
  {
    id: 'itso',
    label: 'Innovation and Technology Support Office',
    short: 'ITSO',
    desc: 'Copyright & citation rigor',
    icon: Lightbulb,
  },
];

export function useEvaluatorWorkstation(
  evaluatorPermissions?: readonly string[] | null,
  userRole = 'faculty',
) {
  const allowedSpecialists = useMemo(() => {
    if (
      userRole === 'admin' ||
      evaluatorPermissions === undefined ||
      evaluatorPermissions === null
    ) {
      return ALL_SPECIALISTS;
    }
    if (evaluatorPermissions.length === 0) {
      return [];
    }
    return ALL_SPECIALISTS.filter((spec) => evaluatorPermissions.includes(spec.id));
  }, [userRole, evaluatorPermissions]);

  const hasSingleSpecialist = allowedSpecialists.length === 1;
  const singleSpecialist = allowedSpecialists[0];

  return {
    allowedSpecialists,
    hasSingleSpecialist,
    singleSpecialist,
  };
}
