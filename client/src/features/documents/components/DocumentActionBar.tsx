import { MagnifyingGlass, Plus } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';

interface DocumentActionBarProps {
  search: string;
  setSearch: (val: string) => void;
}

export function DocumentActionBar({ search, setSearch }: DocumentActionBarProps) {
  return (
    <div className="flex items-center gap-3 border-b border-border bg-surface px-4 sm:px-6 py-2.5">
      <div className="relative flex-1">
        <MagnifyingGlass
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        />
        <input
          type="text"
          className="w-full h-9 border border-input bg-surface pl-9 pr-4 text-xs text-text focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent rounded-sm placeholder:text-text-muted font-medium transition-colors"
          placeholder="Search by module title, course code, or program…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search documents"
        />
      </div>

      <Link
        to="/upload"
        className={cn(
          BUTTON_STYLES.base,
          BUTTON_STYLES.variants.primary,
          BUTTON_STYLES.sizes.sm,
          'shrink-0 h-9 px-3 text-xs',
        )}
      >
        <Plus className="size-3.5" aria-hidden="true" weight="bold" />
        <span>Upload SLM</span>
      </Link>
    </div>
  );
}
