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

const LSPU_SCC_PROGRAM_ALIASES: Record<string, string> = {
  BSIT: 'BSInfoTech',
};

export function isLspuSccProgram(value: string): boolean {
  const normalized = value.trim().toUpperCase();
  const canonical = LSPU_SCC_PROGRAM_ALIASES[normalized] ?? value.trim();
  return ['BSInfoTech', 'BSCS'].some(
    (program) => program.toUpperCase() === canonical.toUpperCase(),
  );
}
