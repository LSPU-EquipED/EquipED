import { describe, expect, it } from 'vitest';
import {
  domainShortLabel,
  formatDomainScore,
  formatPillarWeight,
  formatProgressStatus,
  formatRevisionContext,
  getCompletedDomainCount,
  getDomainProgress,
  getRatingVariant,
  isDomainBlockEvaluated,
  PILLAR_CONFIGS,
  TARGET_DOMAIN_ORDER,
} from '../index';
import type { MatrixDomainScoreBlock } from '../../types';

describe('matrixFormatters', () => {
  describe('formatRevisionContext', () => {
    it('returns "—" for null or undefined or empty record', () => {
      expect(formatRevisionContext(null)).toBe('—');
      expect(formatRevisionContext(undefined)).toBe('—');
      expect(formatRevisionContext({})).toBe('—');
    });

    it('returns formatted versions sorted numerically when versions exist', () => {
      const domainScores: Record<string, MatrixDomainScoreBlock> = {
        sme: { status: 'OK', subtotal: 3.5, max_score: 4, version: 2 },
        coordinator: { status: 'OK', subtotal: 3.8, max_score: 4, version: 1 },
        gad: { status: 'OK', subtotal: 4.0, max_score: 4, version: 2 },
      };
      expect(formatRevisionContext(domainScores)).toBe('Rev 1, 2');
    });

    it('returns legacy notice when blocks exist but have no versions and no snapshots', () => {
      const domainScores: Record<string, MatrixDomainScoreBlock> = {
        sme: { status: 'OK', subtotal: 3.0, max_score: 4 },
      };
      expect(formatRevisionContext(domainScores)).toBe('Legacy — form snapshot unavailable');
    });

    it('returns "—" when snapshots exist but no version numbers', () => {
      const domainScores: Record<string, MatrixDomainScoreBlock> = {
        sme: { status: 'OK', subtotal: 3.0, max_score: 4, form_snapshot_id: 'snap-123' },
      };
      expect(formatRevisionContext(domainScores)).toBe('—');
    });

    it('covers arbitrary dynamic domain keys without assuming fixed agent names', () => {
      const arbitraryDynamicDomains: Record<string, MatrixDomainScoreBlock> = {
        novel_domain_alpha: {
          version: 5,
          form_snapshot_id: 'snap-5',
          subtotal: 4,
          max_score: 4,
          status: 'OK',
        },
        custom_domain_beta: {
          version: 3,
          form_snapshot_id: 'snap-3',
          subtotal: 3.5,
          max_score: 4,
          status: 'OK',
        },
      };
      expect(formatRevisionContext(arbitraryDynamicDomains)).toBe('Rev 3, 5');
    });
  });

  describe('getRatingVariant', () => {
    it('maps ratings to correct status variants', () => {
      expect(getRatingVariant('Very Satisfactory')).toBe('success');
      expect(getRatingVariant('Satisfactory')).toBe('info');
      expect(getRatingVariant('Needs Improvement')).toBe('warning');
      expect(getRatingVariant('Poor')).toBe('destructive');
      expect(getRatingVariant('Unknown')).toBe('neutral');
      expect(getRatingVariant(null)).toBe('neutral');
      expect(getRatingVariant(undefined)).toBe('neutral');
    });
  });

  describe('domainShortLabel', () => {
    it('returns abbreviated labels for known domains', () => {
      expect(domainShortLabel('sme')).toBe('SME');
      expect(domainShortLabel('coordinator')).toBe('Coord');
      expect(domainShortLabel('gad')).toBe('GAD');
      expect(domainShortLabel('itso')).toBe('ITSO');
    });

    it('returns original string for unknown domains', () => {
      expect(domainShortLabel('other')).toBe('other');
    });
  });

  describe('isDomainBlockEvaluated', () => {
    it('returns false for null or undefined', () => {
      expect(isDomainBlockEvaluated(null)).toBe(false);
      expect(isDomainBlockEvaluated(undefined)).toBe(false);
    });

    it('returns false when status is not OK or COMPLETED', () => {
      expect(isDomainBlockEvaluated({ status: 'PENDING', subtotal: 3.5, max_score: 4 })).toBe(false);
      expect(isDomainBlockEvaluated({ status: 'ERROR', subtotal: 3.5, max_score: 4 })).toBe(false);
    });

    it('returns false when subtotal is missing, NaN, or non-finite', () => {
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: null as unknown as number, max_score: 4 })).toBe(false);
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: undefined as unknown as number, max_score: 4 })).toBe(false);
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: Number.NaN, max_score: 4 })).toBe(false);
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: Number.POSITIVE_INFINITY, max_score: 4 })).toBe(false);
    });

    it('returns false when subtotal is out of range 0..4', () => {
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: -0.1, max_score: 4 })).toBe(false);
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: 4.1, max_score: 4 })).toBe(false);
    });

    it('returns true for valid evaluations with status OK or COMPLETED', () => {
      expect(isDomainBlockEvaluated({ status: 'OK', subtotal: 0, max_score: 4 })).toBe(true);
      expect(isDomainBlockEvaluated({ status: 'completed', subtotal: 3.75, max_score: 4 })).toBe(true);
      expect(isDomainBlockEvaluated({ status: 'COMPLETED', subtotal: 4, max_score: 4 })).toBe(true);
    });
  });

  describe('domain progress helpers', () => {
    const sampleScores: Record<string, MatrixDomainScoreBlock> = {
      sme: { status: 'OK', subtotal: 3.5, max_score: 4 },
      coordinator: { status: 'COMPLETED', subtotal: 3.0, max_score: 4 },
      gad: { status: 'PENDING', subtotal: 0, max_score: 4 },
      itso: { status: 'ERROR', subtotal: 2.0, max_score: 4 },
    };

    it('counts completed domains accurately', () => {
      expect(getCompletedDomainCount(null)).toBe(0);
      expect(getCompletedDomainCount(undefined)).toBe(0);
      expect(getCompletedDomainCount(sampleScores)).toBe(2);
    });

    it('computes domain progress correctly', () => {
      expect(getDomainProgress(sampleScores)).toEqual({
        completed: 2,
        total: TARGET_DOMAIN_ORDER.length,
      });
    });

    it('formats progress status strings', () => {
      expect(formatProgressStatus('IN_PROGRESS', sampleScores)).toBe('IN PROGRESS (2/4)');
      expect(formatProgressStatus('in_progress', sampleScores)).toBe('in progress (2/4)');
      expect(formatProgressStatus('COMPLETED', sampleScores)).toBe('COMPLETED');
      expect(formatProgressStatus('PENDING_REVIEW', sampleScores)).toBe('PENDING REVIEW');
    });
  });

  describe('formatDomainScore', () => {
    it('handles null, undefined, and non-finite values', () => {
      expect(formatDomainScore(null)).toBe('—');
      expect(formatDomainScore(undefined)).toBe('—');
      expect(formatDomainScore(Number.NaN)).toBe('—');
      expect(formatDomainScore(Number.POSITIVE_INFINITY)).toBe('—');
    });

    it('omits trailing .00 for integer values', () => {
      expect(formatDomainScore(3)).toBe('3');
      expect(formatDomainScore(3.0)).toBe('3');
      expect(formatDomainScore(0)).toBe('0');
    });

    it('formats fractional values with 2 decimal places', () => {
      expect(formatDomainScore(3.5)).toBe('3.50');
      expect(formatDomainScore(3.75)).toBe('3.75');
      expect(formatDomainScore(3.14159)).toBe('3.14');
    });
  });

  describe('pillarConfig and formatPillarWeight', () => {
    it('provides pillar configurations for all target domains', () => {
      for (const domainId of TARGET_DOMAIN_ORDER) {
        expect(PILLAR_CONFIGS[domainId]).toBeDefined();
        expect(PILLAR_CONFIGS[domainId].id).toBe(domainId);
        expect(PILLAR_CONFIGS[domainId].label).toBeTruthy();
        expect(PILLAR_CONFIGS[domainId].roleTitle).toBeTruthy();
      }
    });

    it('formats weights correctly', () => {
      expect(formatPillarWeight(null)).toBe('Unknown');
      expect(formatPillarWeight(undefined)).toBe('Unknown');
      expect(formatPillarWeight(Number.NaN)).toBe('Unknown');
      expect(formatPillarWeight(0.35)).toBe('35%');
      expect(formatPillarWeight(0.2)).toBe('20%');
      expect(formatPillarWeight(1)).toBe('100%');
      expect(formatPillarWeight(0)).toBe('0%');
      expect(formatPillarWeight(35)).toBe('35%');
      expect(formatPillarWeight(12.5)).toBe('12.5%');
    });
  });
});
