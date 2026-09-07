import { UploadForm } from '../components/UploadForm';

export interface UploadPageProps {
  user?: { displayName?: string } | null;
}

export function UploadPage({ user }: UploadPageProps = {}) {
  return <UploadForm user={user} />;
}
