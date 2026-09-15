import {
  EvaluationHistoryTable,
  type EvaluationHistoryTableProps,
} from '../components/EvaluationHistoryTable';

export function HistoryPage(props: EvaluationHistoryTableProps) {
  return <EvaluationHistoryTable {...props} />;
}
