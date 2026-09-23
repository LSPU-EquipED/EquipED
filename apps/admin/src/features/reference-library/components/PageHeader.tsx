import type { Icon } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';

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
        'relative inline-flex h-11 items-center gap-2 border-b-2 px-1 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
        isActive
          ? 'border-primary text-primary'
          : 'border-transparent text-text-muted hover:border-border-strong hover:text-text',
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}
