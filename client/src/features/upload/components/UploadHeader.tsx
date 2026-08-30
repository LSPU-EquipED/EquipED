import { Badge } from '@/shared/components/Badge';

interface UploadHeaderProps {
  title: string;
}

export function UploadHeader({ title }: UploadHeaderProps) {
  return (
    <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6 bg-surface-subtle/50">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Document Workspace
        </p>
        <h2 className="truncate text-sm font-semibold text-text mt-0.5">
          {title.trim() || 'Untitled document upload'}
        </h2>
      </div>
      <Badge variant="neutral" className="uppercase tracking-wider text-[10px]">
        Upload only • evaluation later
      </Badge>
    </div>
  );
}
