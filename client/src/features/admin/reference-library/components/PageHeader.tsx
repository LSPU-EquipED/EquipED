import { Link } from '@tanstack/react-router';
import { UploadSimple, type Icon } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';

export function PageHeader() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">Admin</p>
        <h1 className="mt-1 text-xl font-bold text-text">Reference Library</h1>
        <p className="mt-1 text-xs text-text-muted font-medium">
          Manage shared syllabus, curriculum, and policy references used by evaluations.
        </p>
      </div>
      <Link
        to="/admin/ingest"
        className="inline-flex h-10 items-center gap-2 bg-primary px-4 text-sm font-semibold uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-ring rounded-sm"
      >
        <UploadSimple className="size-4" />
        Upload reference
      </Link>
    </div>
  );
}

interface LibraryTabButtonProps {
  id: string;
  isActive: boolean;
  onSelect: () => void;
  label: string;
  icon: Icon;
}

export function LibraryTabButton({
  id,
  isActive,
  onSelect,
  label,
  icon: Icon,
}: LibraryTabButtonProps) {
  return (
    <button
      id={id}
      role="tab"
      type="button"
      aria-selected={isActive}
      onClick={onSelect}
      className={cn(
        'inline-flex h-9 items-center gap-2 border-b-2 px-3 text-sm font-semibold uppercase tracking-wider transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm',
        isActive
          ? 'border-primary text-text'
          : 'border-transparent text-text-muted hover:border-border hover:text-text',
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      {label}
    </button>
  );
}
