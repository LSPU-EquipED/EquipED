import type { Icon } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';

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
        'inline-flex h-8.5 items-center gap-2 px-3.5 rounded-xs text-xs sm:text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
        isActive
          ? 'bg-surface text-text shadow-xs border border-border'
          : 'text-text-muted hover:text-text border border-transparent',
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}
