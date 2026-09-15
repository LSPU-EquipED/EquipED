export type ProgramEntry = {
  code: string;
  name: string;
};

export type ProgramCollegeGroup = {
  code: string;
  college: string;
  programs: ProgramEntry[];
};

export const LSPU_SCC_COLLEGE_PROGRAMS: ProgramCollegeGroup[] = [
  {
    code: 'CCS',
    college: 'College of Computer Studies',
    programs: [
      { code: 'BSInfoTech', name: 'Bachelor of Science in Information Technology' },
      { code: 'BSCS', name: 'Bachelor of Science in Computer Science' },
    ],
  },
];

export const CANONICAL_PROGRAMS = ['BSCS', 'BSInfoTech'] as const;
export type CanonicalProgram = (typeof CANONICAL_PROGRAMS)[number];

const PROGRAM_NORMALIZATION_MAP: Record<string, string> = {
  BSCS: 'BSCS',
  BSINFOTECH: 'BSInfoTech',
  BSIT: 'BSInfoTech',
};

/**
 * Normalizes client read/display program strings to their canonical form.
 * E.g., 'BSIT', 'BSINFOTECH', 'bsit', 'bscs' -> 'BSInfoTech', 'BSCS'.
 * Preserves unmapped trimmed strings for downstream handling.
 */
export function normalizeProgram(value: string): string {
  const trimmed = value.trim();
  const upper = trimmed.toUpperCase();
  return PROGRAM_NORMALIZATION_MAP[upper] ?? trimmed;
}

export function isLspuSccProgram(value: string): boolean {
  if (!value || typeof value !== 'string') return false;
  const normalized = normalizeProgram(value);
  return CANONICAL_PROGRAMS.some(
    (program) => program.toUpperCase() === normalized.toUpperCase(),
  );
}
