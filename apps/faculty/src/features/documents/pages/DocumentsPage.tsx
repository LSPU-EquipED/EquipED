import type { TargetAgent } from '@/shared/types/evaluations';

import { DocumentDashboard } from '../components/DocumentDashboard';

export function DocumentsPage({ targetAgent = 'sme' }: { targetAgent?: TargetAgent }) {
  return (
    <div className="w-full min-h-full bg-canvas">
      <DocumentDashboard targetAgent={targetAgent} />
    </div>
  );
}
