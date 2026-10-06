import type { ModelValidationItem } from '../types';
import { criterionKey } from './helpers';

export interface CompareChip {
  key: string;
  label: string;
  skipped: boolean;
}

export interface CompareRow {
  label: string;
  base: string;
  adapter: string;
  result: string;
  /** Which side wins this row; null when the row is not a better/worse measure. */
  better: Side | null;
}

export type Side = 'base' | 'adapter' | 'tie';

export type CompareVerdict = 'closer' | 'same' | 'farther';

export interface PairComparison {
  winner: Side | null;
  /** Criteria left out because the two runs carry different expected scores. */
  differingExpected: string[];
  status: 'ok' | 'no-overlap' | 'all-skipped';
  chips: CompareChip[];
  rows: CompareRow[];
  summary: string;
  includedCount: number;
  baseMeanError: number | null;
  adapterMeanError: number | null;
  errorVerdict: CompareVerdict | null;
  baseExact: number;
  adapterExact: number;
  baseAverage: number | null;
  adapterAverage: number | null;
  closerCount: number;
  sameCount: number;
  fartherCount: number;
}

const EPSILON = 1e-9;

/** Key used for a criterion's skip chip: the same (agent, criterion) pair we match on. */
export const compareChipKey = (agentId: string, criterionId: string) =>
  criterionKey(agentId, criterionId);

const side = (base: number, adapter: number, lowerIsBetter: boolean): Side => {
  const round = (v: number) => Math.round(v * 100) / 100;
  if (Math.abs(round(base) - round(adapter)) < EPSILON) return 'tie';
  return (adapter < base) === lowerIsBetter ? 'adapter' : 'base';
};

/** Overall winner: lower mean error first, exact matches only if the errors are equal. */
export function decideWinner(
  baseMeanError: number | null,
  adapterMeanError: number | null,
  baseExact: number,
  adapterExact: number,
): Side | null {
  if (baseMeanError == null || adapterMeanError == null) return null;
  const byError = side(baseMeanError, adapterMeanError, true);
  if (byError !== 'tie') return byError;
  return side(baseExact, adapterExact, false);
}

const fixed = (value: number) => value.toFixed(2);
const signed = (value: number, digits: number) => {
  const text = Math.abs(value).toFixed(digits);
  if (Number(text) === 0) return text;
  return `${value > 0 ? '+' : '-'}${text}`;
};

export function computePairComparison(
  baseItem: ModelValidationItem,
  adapterItem: ModelValidationItem,
  skipped: Set<string>,
): PairComparison {
  const adapterByKey = new Map(
    adapterItem.criterion_scores.map((s) => [compareChipKey(s.agent_id, s.criterion_id), s]),
  );

  const chips: CompareChip[] = [];
  const differingExpected: string[] = [];
  const pairs: { expected: number; base: number; adapter: number }[] = [];
  for (const b of baseItem.criterion_scores) {
    const key = compareChipKey(b.agent_id, b.criterion_id);
    const a = adapterByKey.get(key);
    if (!a || b.actual_score == null || a.actual_score == null) continue;
    if (typeof b.expected_score !== 'number' || !Number.isFinite(b.expected_score)) continue;
    if (typeof a.expected_score !== 'number' || !Number.isFinite(a.expected_score)) continue;
    if (a.expected_score !== b.expected_score) {
      differingExpected.push(b.criterion_id);
      continue;
    }
    const isSkipped = skipped.has(key);
    chips.push({ key, label: `${b.agent_id.toUpperCase()} ${b.criterion_id}`, skipped: isSkipped });
    if (!isSkipped) {
      pairs.push({ expected: b.expected_score, base: b.actual_score, adapter: a.actual_score });
    }
  }

  const empty: PairComparison = {
    winner: null,
    differingExpected,
    status: chips.length === 0 ? 'no-overlap' : 'all-skipped',
    chips,
    rows: [],
    summary: '',
    includedCount: 0,
    baseMeanError: null,
    adapterMeanError: null,
    errorVerdict: null,
    baseExact: 0,
    adapterExact: 0,
    baseAverage: null,
    adapterAverage: null,
    closerCount: 0,
    sameCount: 0,
    fartherCount: 0,
  };
  if (pairs.length === 0) return empty;

  const n = pairs.length;
  const sum = (values: number[]) => values.reduce((total, v) => total + v, 0);
  const baseErrors = pairs.map((p) => Math.abs(p.base - p.expected));
  const adapterErrors = pairs.map((p) => Math.abs(p.adapter - p.expected));
  const baseMeanError = sum(baseErrors) / n;
  const adapterMeanError = sum(adapterErrors) / n;
  const diff = adapterMeanError - baseMeanError;
  const errorVerdict: CompareVerdict =
    Math.abs(diff) < EPSILON ? 'same' : diff < 0 ? 'closer' : 'farther';

  let closerCount = 0;
  let sameCount = 0;
  let fartherCount = 0;
  baseErrors.forEach((be, i) => {
    const d = adapterErrors[i] - be;
    if (Math.abs(d) < EPSILON) sameCount += 1;
    else if (d < 0) closerCount += 1;
    else fartherCount += 1;
  });

  const baseExact = pairs.filter((p) => p.base === p.expected).length;
  const adapterExact = pairs.filter((p) => p.adapter === p.expected).length;
  const baseAverage = sum(pairs.map((p) => p.base)) / n;
  const adapterAverage = sum(pairs.map((p) => p.adapter)) / n;

  const rows: CompareRow[] = [
    {
      label: 'Mean error vs expected',
      base: fixed(baseMeanError),
      adapter: fixed(adapterMeanError),
      result: errorVerdict.toUpperCase(),
      better: side(baseMeanError, adapterMeanError, true),
    },
    {
      label: 'Exact matches',
      base: `${baseExact} of ${n}`,
      adapter: `${adapterExact} of ${n}`,
      result: signed(adapterExact - baseExact, 0),
      better: side(baseExact, adapterExact, false),
    },
    {
      label: 'Criteria: closer / same / farther',
      base: '',
      adapter: '',
      result: `${closerCount} / ${sameCount} / ${fartherCount}`,
      better: null,
    },
    {
      label: 'Average score',
      base: fixed(baseAverage),
      adapter: fixed(adapterAverage),
      result: signed(adapterAverage - baseAverage, 2),
      better: null,
    },
  ];

  return {
    differingExpected,
    winner: decideWinner(baseMeanError, adapterMeanError, baseExact, adapterExact),
    status: 'ok',
    chips,
    rows,
    summary: `The adapter got closer to the expected scores on ${closerCount} criteria, stayed the same on ${sameCount} and moved away on ${fartherCount}.`,
    includedCount: n,
    baseMeanError,
    adapterMeanError,
    errorVerdict,
    baseExact,
    adapterExact,
    baseAverage,
    adapterAverage,
    closerCount,
    sameCount,
    fartherCount,
  };
}
