// Pure helpers for the Model Validation confusion matrix. The page component
// imports the same functions; tests cover the boundary between "the API
// provided a real matrix" and "we fabricated one from scratch".

export const CONFUSION_MATRIX_SIZE = 4;

export type ConfusionMatrixMetrics = {
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
};

export const emptyConfusionMatrix = (): number[][] =>
  Array.from({ length: CONFUSION_MATRIX_SIZE }, () =>
    Array.from({ length: CONFUSION_MATRIX_SIZE }, () => 0),
  );

/**
 * Returns true only when the API has supplied a real, comparable matrix —
 * a 4×4 grid with at least one non-zero cell. A missing key, the wrong
 * shape, or a fully zero grid all indicate "no data" and the UI must
 * not invent one in their place.
 *
 * The `matrix is number[][]` type predicate lets callers narrow an
 * `agentMatrices?.[id]` lookup to a non-null array without a separate
 * `if (matrix)` guard, so the truthy branch can pass the matrix
 * straight to `calculateConfusionMatrixMetrics` without the metrics
 * ever seeing a malformed value.
 */
export function hasConfusionMatrixData(
  matrix: number[][] | undefined | null,
): matrix is number[][] {
  if (!matrix || matrix.length !== CONFUSION_MATRIX_SIZE) return false;
  // Validate the full shape up front so a malformed row cannot be
  // masked by an earlier valid row. Any wrong-sized row means the API
  // did not give us a trustworthy matrix to render.
  for (const row of matrix) {
    if (!row || row.length !== CONFUSION_MATRIX_SIZE) return false;
  }
  for (const row of matrix) {
    for (const cell of row) {
      if (typeof cell === 'number' && cell > 0) return true;
    }
  }
  return false;
}

export function calculateConfusionMatrixMetrics(matrix: number[][]): ConfusionMatrixMetrics {
  const size = matrix.length;
  const total = matrix.reduce(
    (matrixTotal, row) => matrixTotal + row.reduce((rowTotal, count) => rowTotal + count, 0),
    0,
  );

  if (total === 0) {
    return { accuracy: null, precision: null, recall: null };
  }

  let exactMatches = 0;
  const precisionByClass: number[] = [];
  const recallByClass: number[] = [];

  for (let classIndex = 0; classIndex < size; classIndex += 1) {
    const truePositives = matrix[classIndex]?.[classIndex] ?? 0;
    const predictedCount = matrix.reduce((sum, row) => sum + (row[classIndex] ?? 0), 0);
    const expectedCount = matrix[classIndex]?.reduce((sum, count) => sum + count, 0) ?? 0;

    exactMatches += truePositives;
    if (predictedCount > 0) precisionByClass.push(truePositives / predictedCount);
    if (expectedCount > 0) recallByClass.push(truePositives / expectedCount);
  }

  const average = (values: number[]) =>
    values.length > 0 ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

  return {
    accuracy: exactMatches / total,
    precision: average(precisionByClass),
    recall: average(recallByClass),
  };
}
