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
    code: 'CAS',
    college: 'College of Arts and Science',
    programs: [
      { code: 'BA-AB', name: 'Bachelor of Arts in Broadcasting' },
      { code: 'BSBio', name: 'Bachelor of Science in Biology' },
      { code: 'BSChem', name: 'Bachelor of Science in Chemistry' },
      { code: 'BSMath', name: 'Bachelor of Science in Mathematics' },
      { code: 'BSPsych', name: 'Bachelor of Science in Psychology' },
    ],
  },
  {
    code: 'CBAA',
    college: 'College of Business Administration and Accountancy',
    programs: [
      { code: 'BSOA', name: 'Bachelor of Science in Office Administration' },
      { code: 'BSE', name: 'Bachelor of Science in Entrepreneurship' },
      { code: 'BSA', name: 'Bachelor of Science in Accountancy' },
      { code: 'MPA', name: 'Master in Public Administration' },
    ],
  },
  {
    code: 'CCS',
    college: 'College of Computer Studies',
    programs: [
      { code: 'BSInfoTech', name: 'Bachelor of Science in Information Technology' },
      { code: 'BSCS', name: 'Bachelor of Science in Computer Science' },
      { code: 'MSIT', name: 'Master in Information Technology' },
    ],
  },
  {
    code: 'CCJE',
    college: 'College of Criminal Justice Education',
    programs: [{ code: 'BSCrim', name: 'Bachelor of Science in Criminology' }],
  },
  {
    code: 'COE',
    college: 'College of Engineering',
    programs: [
      { code: 'BSECE', name: 'Bachelor of Science in Electronics Engineering' },
      { code: 'BSME', name: 'Bachelor of Science in Mechanical Engineering' },
      { code: 'BSEE', name: 'Bachelor of Science in Electrical Engineering' },
      { code: 'BSCE', name: 'Bachelor of Science in Civil Engineering' },
      { code: 'BSCpE', name: 'Bachelor of Science in Computer Engineering' },
    ],
  },
  {
    code: 'CIT',
    college: 'College of Industrial Technology',
    programs: [{ code: 'BSInTech', name: 'Bachelor of Science in Industrial Technology' }],
  },
  {
    code: 'CHMT',
    college: 'College of Hospitality Management and Tourism',
    programs: [
      { code: 'BSHM', name: 'Bachelor of Science in Hospitality Management' },
      { code: 'BSTM', name: 'Bachelor of Science in Tourism Management' },
    ],
  },
  {
    code: 'COL',
    college: 'College of Law',
    programs: [{ code: 'JD', name: 'Juris Doctor' }],
  },
  {
    code: 'CONAH',
    college: 'College of Nursing and Allied Health',
    programs: [{ code: 'BSN', name: 'Bachelor of Science in Nursing' }],
  },
  {
    code: 'CTE',
    college: 'College of Teacher Education',
    programs: [
      { code: 'BSEd', name: 'Bachelor of Secondary Education' },
      { code: 'BEEd', name: 'Bachelor of Elementary Education' },
      { code: 'BTVTEd', name: 'Bachelor of Technical Vocational Teacher Education' },
      { code: 'BPEd', name: 'Bachelor of Physical Education' },
      { code: 'BTLEd', name: 'Bachelor of Technology and Livelihood Education' },
      { code: 'EdD', name: 'Doctor of Education' },
      { code: 'MAT-ENG', name: 'Master of Arts in Teaching English' },
      { code: 'MAEd', name: 'Master of Arts in Education' },
    ],
  },
];

export function isLspuSccProgram(value: string): boolean {
  const normalized = value.trim().toUpperCase();
  return LSPU_SCC_COLLEGE_PROGRAMS.some((group) =>
    group.programs.some((program) => program.code.toUpperCase() === normalized),
  );
}
