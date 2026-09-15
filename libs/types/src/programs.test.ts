import { describe, expect, it } from 'vitest';
import {
  CANONICAL_PROGRAMS,
  LSPU_SCC_COLLEGE_PROGRAMS,
  isLspuSccProgram,
  normalizeProgram,
} from '../programs';

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

  it('exposes exact canonical programs list', () => {
    expect(CANONICAL_PROGRAMS).toEqual(['BSCS', 'BSInfoTech']);
  });

  it('normalizes program read/display aliases to canonical constants', () => {
    expect(normalizeProgram('BSCS')).toBe('BSCS');
    expect(normalizeProgram('  bscs ')).toBe('BSCS');
    expect(normalizeProgram('BSInfoTech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSINFOTECH')).toBe('BSInfoTech');
    expect(normalizeProgram('bsinfotech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSIT')).toBe('BSInfoTech');
    expect(normalizeProgram('  bsit  ')).toBe('BSInfoTech');
    expect(normalizeProgram('  BSIS  ')).toBe('BSIS');
    expect(normalizeProgram('')).toBe('');
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
