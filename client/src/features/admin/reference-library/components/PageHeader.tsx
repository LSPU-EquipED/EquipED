import { Link } from '@tanstack/react-router';
import { BookOpen, Upload } from 'lucide-react';
import { cn } from '@/shared/components/utils';

export function PageHeader() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
        <h1 className="mt-1 text-xl font-bold text-slate-900">Reference Library</h1>
        <p className="mt-1 text-xs text-slate-500 font-medium">
          Manage shared syllabus, curriculum, and policy references used by evaluations.
        </p>
      </div>
      <Link
        to="/admin/ingest"
        className="inline-flex h-10 items-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm"
      >
        <Upload className="size-4" />
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
  icon: typeof BookOpen;
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
        'inline-flex h-9 items-center gap-2 border-b-2 px-3 text-sm font-semibold uppercase tracking-wider transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm',
        isActive
          ? 'border-[#1b3b87] text-slate-900'
          : 'border-transparent text-slate-500 hover:border-slate-200 hover:text-slate-700',
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      {label}
    </button>
  );
}
