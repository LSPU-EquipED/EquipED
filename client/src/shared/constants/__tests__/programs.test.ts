import { describe, expect, it } from 'vitest';
import { LSPU_SCC_COLLEGE_PROGRAMS, isLspuSccProgram } from '../programs';

describe('LSPU SCC programs', () => {
  it('exposes only the two CCS programs in canonical order', () => {
    expect(LSPU_SCC_COLLEGE_PROGRAMS).toHaveLength(1);
    expect(LSPU_SCC_COLLEGE_PROGRAMS[0]).toMatchObject({
      code: 'CCS',
      college: 'College of Computer Studies',
    });
    expect(LSPU_SCC_COLLEGE_PROGRAMS[0].programs.map((program) => program.code)).toEqual([
      'BSInfoTech',
      'BSCS',
    ]);
  });

  it.each(['BSInfoTech', 'bsinfotech', 'BSCS', 'bscs', 'BSIT', 'bsit'])(
    '%s is accepted',
    (value) => {
      expect(isLspuSccProgram(value)).toBe(true);
    },
  );

  it.each(['BSEd', 'MSIT', 'BSN', '', '   '])('%j is rejected', (value) => {
    expect(isLspuSccProgram(value)).toBe(false);
  });
});
