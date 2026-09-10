import type { TargetAgent } from '@/shared/types/evaluations';

import { UploadForm } from '../components/UploadForm';

export interface UploadPageProps {
  user?: { displayName?: string } | null;
  targetAgent?: TargetAgent;
}

export function UploadPage({ user, targetAgent = 'sme' }: UploadPageProps = {}) {
  return <UploadForm user={user} targetAgent={targetAgent} />;
}
