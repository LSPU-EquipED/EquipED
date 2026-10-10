import type { TrainingSummary } from '../types';
import { buildTrainingSummaryEntries } from '../utils/trainingData.utils';
import { TrainingRecordMetadata } from './TrainingRecordMetadata';

export function TrainingSummaryPanel({ summary }: { summary?: TrainingSummary | null }) {
  const entries = buildTrainingSummaryEntries(summary);
  return (
    <section aria-label="Training summary" className="space-y-2">
      <p className="text-[13px] font-medium leading-5 text-text">Training summary</p>
      {entries.length === 0 ? (
        <p className="text-[13px] leading-5 text-text-muted">Not recorded</p>
      ) : (
        <>
          <TrainingRecordMetadata entries={entries} tabularValues />
          <p className="text-xs leading-5 text-text-muted">
            Measured on the training examples. It shows the model learned the corrections, not how
            it scores new documents.
          </p>
        </>
      )}
    </section>
  );
}
