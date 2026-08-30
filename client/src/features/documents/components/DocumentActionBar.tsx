import { Search, Upload } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';

interface DocumentActionBarProps {
  search: string;
  setSearch: (val: string) => void;
}

export function DocumentActionBar({ search, setSearch }: DocumentActionBarProps) {
  return (
    <div className="flex items-center gap-4 border-b border-border bg-surface-subtle/50 px-6 md:px-8 py-3">
      <div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        />
        <input
          type="text"
          className="w-full h-10 border border-input bg-surface pl-9 pr-4 text-sm text-text focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent rounded-sm placeholder:text-text-muted font-medium transition-colors"
          placeholder="Search title, course, program…"
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
          BUTTON_STYLES.sizes.md,
          'text-xs font-bold tracking-wider uppercase shrink-0',
        )}
      >
        <Upload className="size-3.5" aria-hidden="true" />
        Upload SLM
      </Link>
    </div>
  );
}
