// Unit tests for the pure confusion matrix helpers used by
// `ModelValidationPage`. These guard the boundary between "the API
// provided a real, comparable matrix" and "we are about to fabricate
// one from an empty / all-zero grid".
import { describe, expect, it } from 'vitest';
import {
  CONFUSION_MATRIX_SIZE,
  calculateConfusionMatrixMetrics,
  emptyConfusionMatrix,
  hasConfusionMatrixData,
} from '../confusionMatrix';

const populatedMatrix = (): number[][] => [
  [3, 0, 0, 0],
  [0, 4, 1, 0],
  [0, 1, 2, 1],
  [0, 0, 0, 1],
];

describe('hasConfusionMatrixData', () => {
  it('rejects undefined, null, and the placeholder empty matrix', () => {
    expect(hasConfusionMatrixData(undefined)).toBe(false);
    expect(hasConfusionMatrixData(null)).toBe(false);
    expect(hasConfusionMatrixData(emptyConfusionMatrix())).toBe(false);
  });

  it('rejects grids with the wrong shape', () => {
    expect(hasConfusionMatrixData([])).toBe(false);
    expect(hasConfusionMatrixData([[1, 0, 0, 0]])).toBe(false);
    expect(
      hasConfusionMatrixData([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
        [0, 0, 0],
      ]),
    ).toBe(false);
    expect(
      hasConfusionMatrixData([
        [1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
      ]),
    ).toBe(false);
  });

  it('rejects rows that are missing or the wrong length', () => {
    const matrix = populatedMatrix();
    const broken: number[][] = [matrix[0]!, [0, 0, 0], matrix[2]!, matrix[3]!];
    expect(hasConfusionMatrixData(broken)).toBe(false);
  });

  it('returns true for a matrix with at least one non-zero cell', () => {
    const matrix = emptyConfusionMatrix();
    matrix[2]![2] = 1;
    expect(hasConfusionMatrixData(matrix)).toBe(true);
  });

  it('returns true for a fully populated matrix', () => {
    expect(hasConfusionMatrixData(populatedMatrix())).toBe(true);
  });

  it('does not treat negative or non-numeric values as comparable data', () => {
    const matrix = populatedMatrix();
    // Replace the only positive cell with -1; the API would never send
    // a negative count, but the helper should still report "no data" if
    // every numeric value is <= 0.
    const onlyNegatives = matrix.map((row) => row.map((cell) => (cell > 0 ? -cell : cell)));
    expect(hasConfusionMatrixData(onlyNegatives)).toBe(false);
  });
});

describe('emptyConfusionMatrix', () => {
  it('returns a 4x4 grid of zeros', () => {
    const matrix = emptyConfusionMatrix();
    expect(matrix.length).toBe(CONFUSION_MATRIX_SIZE);
    for (const row of matrix) {
      expect(row.length).toBe(CONFUSION_MATRIX_SIZE);
      for (const cell of row) {
        expect(cell).toBe(0);
      }
    }
  });
});

describe('calculateConfusionMatrixMetrics', () => {
  it('reports null metrics for an all-zero matrix', () => {
    expect(calculateConfusionMatrixMetrics(emptyConfusionMatrix())).toEqual({
      accuracy: null,
      precision: null,
      recall: null,
    });
  });

  it('derives accuracy from exact diagonal matches', () => {
    const matrix = [
      [2, 0, 0, 0],
      [0, 2, 0, 0],
      [0, 0, 2, 0],
      [0, 0, 0, 2],
    ];
    const metrics = calculateConfusionMatrixMetrics(matrix);
    expect(metrics.accuracy).toBe(1);
    expect(metrics.precision).toBe(1);
    expect(metrics.recall).toBe(1);
  });

  it('averages precision and recall only over classes with a denominator', () => {
    // Class 0: 2 hits on the diagonal, 1 off-diagonal prediction
    //          → precision 2/3, recall 1.
    // Class 1: predicted once into class 0, expected once
    //          → precision skipped (no predicted positives), recall 0.
    // Class 2: predicted once into class 3, expected once
    //          → precision skipped (no predicted positives), recall 0.
    // Class 3: predicted once, never expected
    //          → precision 0/1, recall skipped (no expected positives).
    const matrix = [
      [2, 0, 0, 0],
      [1, 0, 0, 0],
      [0, 0, 0, 1],
      [0, 0, 0, 0],
    ];
    const metrics = calculateConfusionMatrixMetrics(matrix);
    // 4 comparable cells total, 2 land on the diagonal.
    expect(metrics.accuracy).toBe(2 / 4);
    // Precision: class 0 = 2/3, class 3 = 0; classes 1 and 2 are skipped
    // because they have no predicted positives. Macro average over the
    // two contributing classes → 1/3.
    expect(metrics.precision).toBeCloseTo(1 / 3, 6);
    // Recall: class 0 = 1, class 1 = 0, class 2 = 0; class 3 is skipped
    // because it has no expected positives. Macro average over the
    // three contributing classes → 1/3.
    expect(metrics.recall).toBeCloseTo(1 / 3, 6);
  });
});

describe('per-agent breakdown safety contract', () => {
  // The page uses these two helpers together: it only ever feeds a
  // per-agent matrix into `calculateConfusionMatrixMetrics` when
  // `hasConfusionMatrixData` confirms it is a real 4×4 grid with at
  // least one counted cell. When the API returns a missing key, the
  // wrong shape, or a fully zero grid, the page substitutes a fresh
  // empty matrix so the metric helper reports `unavailable` instead
  // of producing numbers from a shape that does not match the
  // institutional 1–4 scale.

  const malformedInputs: Array<{ label: string; matrix: unknown }> = [
    { label: 'undefined', matrix: undefined },
    { label: 'null', matrix: null },
    { label: 'all-zero grid', matrix: emptyConfusionMatrix() },
    {
      label: 'missing row',
      matrix: [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
      ],
    },
    {
      label: 'short row hidden by a valid neighbour',
      matrix: [populatedMatrix()[0]!, [0, 0, 0], populatedMatrix()[2]!, populatedMatrix()[3]!],
    },
    { label: '5x5 grid', matrix: Array.from({ length: 5 }, () => [0, 0, 0, 0, 0]) },
  ];

  it.each(malformedInputs)(
    'falls back to unavailable metrics when the API returns $label',
    ({ matrix }) => {
      // Page-level contract: a malformed input is rejected by the gate
      // and replaced with a fresh empty matrix before metrics are
      // computed, so the helper never sees a non-null bad value.
      const isAccepted = hasConfusionMatrixData(matrix as number[][] | undefined | null);
      expect(isAccepted).toBe(false);

      const safeMatrix = isAccepted ? (matrix as number[][]) : emptyConfusionMatrix();
      expect(calculateConfusionMatrixMetrics(safeMatrix)).toEqual({
        accuracy: null,
        precision: null,
        recall: null,
      });
    },
  );

  it('does not throw when calculateConfusionMatrixMetrics sees a malformed non-null matrix directly', () => {
    // Defensive: even if a future caller forgets the gate, the helper
    // itself must never throw on the API shapes the page already
    // routes to the "unavailable" branch.
    const broken = [populatedMatrix()[0]!, [0, 0, 0], populatedMatrix()[2]!, populatedMatrix()[3]!];
    expect(() => calculateConfusionMatrixMetrics(broken)).not.toThrow();
  });
});
