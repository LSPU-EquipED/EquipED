import { useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  CaretDown,
  Check,
  CheckCircle,
  Clock,
  MagnifyingGlass,
  Spinner,
  X,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { useSpecialistQueue } from '../hooks/useSpecialistQueue';
import type { DeskQueueItem } from '../types';
import type { TargetAgent } from '@/shared/types/evaluations';

export interface SpecialistQueueSwitcherProps {
  targetAgent: TargetAgent;
  selectedDocumentId?: string | null;
  onSelectDocument: (documentId: string) => void;
  program?: string;
  id?: string;
  className?: string;
  disabled?: boolean;
  /** Direct items override (useful for testing or standalone usage) */
  items?: DeskQueueItem[];
  /** Fallback documents when queue API returns empty */
  fallbackDocuments?: Array<{
    documentId: string;
    title: string;
    courseCode?: string | null;
    program?: string | null;
    uploadedAt?: string | null;
  }>;
}


function formatUploadDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

function formatDeskScore(score: number | null | undefined): string {
  if (score == null) return '0.00';
  return Number(score).toFixed(2);
}

function DeskStatusBadge({
  status,
  score,
}: {
  status: string;
  score: number | null;
}) {
  const norm = (status || 'READY').toUpperCase();
  if (norm === 'EVALUATING') {
    return (
      <Badge variant="info" className="gap-1 text-[11px] font-medium py-0.5">
        <Spinner className="size-3 animate-spin" aria-hidden="true" />
        <span>Evaluating…</span>
      </Badge>
    );
  }
  if (norm === 'COMPLETED') {
    return (
      <Badge variant="success" className="gap-1 text-[11px] font-medium py-0.5">
        <CheckCircle className="size-3" weight="fill" aria-hidden="true" />
        <span>Evaluated {formatDeskScore(score)}/4.00</span>
      </Badge>
    );
  }
  if (norm === 'FAILED') {
    return (
      <Badge variant="destructive" className="gap-1 text-[11px] font-medium py-0.5">
        <span>Failed</span>
      </Badge>
    );
  }
  return (
    <Badge variant="warning" className="gap-1 text-[11px] font-medium py-0.5">
      <Clock className="size-3" aria-hidden="true" />
      <span>Ready for Review</span>
    </Badge>
  );
}


type FilterChip = 'all' | 'pending' | 'completed';

export function SpecialistQueueSwitcher({
  targetAgent,
  selectedDocumentId,
  onSelectDocument,
  program,
  id: idProp,
  className,
  disabled = false,
  items: propItems,
  fallbackDocuments,
}: SpecialistQueueSwitcherProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listboxId = `${id}-listbox`;
  const searchInputId = `${id}-search`;

  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterChip>('all');
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const { data: queueData, isLoading: isLoadingQueue } = useSpecialistQueue(
    targetAgent,
    program,
    { enabled: !propItems },
  );

  const allItems = useMemo<DeskQueueItem[]>(() => {
    if (propItems) return propItems;
    if (queueData?.items && queueData.items.length > 0) {
      return queueData.items;
    }
    if (fallbackDocuments && fallbackDocuments.length > 0) {
      return fallbackDocuments.map((doc) => ({
        document_id: doc.documentId,
        title: doc.title,
        course_code: doc.courseCode ?? null,
        program: doc.program ?? null,
        uploaded_at: doc.uploadedAt ?? '',
        my_status: 'READY',
        my_score: null,
        my_adjectival: null,
        peer_completed_count: 0,
        peer_completed_desks: [],
      }));
    }
    return [];
  }, [propItems, queueData, fallbackDocuments]);

  const counts = useMemo(() => {
    let pending = 0;
    let completed = 0;
    for (const item of allItems) {
      if ((item.my_status || '').toUpperCase() === 'COMPLETED') {
        completed++;
      } else {
        pending++;
      }
    }
    return { all: allItems.length, pending, completed };
  }, [allItems]);

  const filteredItems = useMemo(() => {
    let result = allItems;
    if (activeFilter === 'pending') {
      result = result.filter((i) => (i.my_status || '').toUpperCase() !== 'COMPLETED');
    } else if (activeFilter === 'completed') {
      result = result.filter((i) => (i.my_status || '').toUpperCase() === 'COMPLETED');
    }

    const trimmed = searchQuery.trim().toLowerCase();
    if (trimmed) {
      result = result.filter((item) => {
        const titleMatch = item.title?.toLowerCase().includes(trimmed);
        const codeMatch = item.course_code?.toLowerCase().includes(trimmed);
        return Boolean(titleMatch || codeMatch);
      });
    }

    return result;
  }, [allItems, activeFilter, searchQuery]);

  const selectedItem = useMemo(
    () => allItems.find((i) => i.document_id === selectedDocumentId) ?? null,
    [allItems, selectedDocumentId],
  );

  const safeHighlightedIndex = Math.min(
    highlightedIndex,
    Math.max(0, filteredItems.length - 1),
  );

  const openPicker = () => {
    if (disabled) return;
    setIsOpen(true);
    setSearchQuery('');
    setActiveFilter('all');
    const selectedIdx = filteredItems.findIndex(
      (item) => item.document_id === selectedDocumentId,
    );
    setHighlightedIndex(selectedIdx >= 0 ? selectedIdx : 0);
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  };

  const closePicker = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const handleSelect = (documentId: string) => {
    onSelectDocument(documentId);
    closePicker();
  };
  useEffect(() => {
    if (!isOpen) return;
    const activeEl = itemRefs.current[safeHighlightedIndex];
    activeEl?.scrollIntoView?.({ block: 'nearest' });
  }, [isOpen, safeHighlightedIndex]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    const count = filteredItems.length;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (count > 0) {
        setHighlightedIndex((prev) => (prev + 1) % count);
      }
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (count > 0) {
        setHighlightedIndex((prev) => (prev - 1 + count) % count);
      }
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const target = filteredItems[safeHighlightedIndex];
      if (target) {
        handleSelect(target.document_id);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closePicker();
    }
  };

  const triggerLabel = selectedItem
    ? `${selectedItem.course_code ? `${selectedItem.course_code} — ` : ''}${selectedItem.title}`
    : isLoadingQueue && !propItems
      ? 'Loading queue…'
      : allItems.length === 0
        ? 'No modules available'
        : 'Select a module…';

  return (
    <div ref={containerRef} className={cn('relative inline-block text-left', className)}>
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        disabled={disabled || (allItems.length === 0 && !isLoadingQueue)}
        onClick={() => (isOpen ? closePicker() : openPicker())}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-label="Active SLM"
        className={cn(
          'flex h-9 w-72 sm:w-80 items-center justify-between gap-2 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors',
          'hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer select-none',
          disabled && 'opacity-50 pointer-events-none',
        )}
      >
        <span className="truncate text-left">{triggerLabel}</span>
        <div className="flex items-center gap-1.5 shrink-0 text-text-muted">
          {selectedItem && (
            <span
              className={cn(
                'size-2 rounded-full',
                (selectedItem.my_status || '').toUpperCase() === 'COMPLETED'
                  ? 'bg-success'
                  : (selectedItem.my_status || '').toUpperCase() === 'EVALUATING'
                    ? 'bg-info animate-pulse'
                    : 'bg-warning',
              )}
              aria-hidden="true"
            />
          )}
          <CaretDown
            className={cn('size-3.5 transition-transform duration-150', isOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </div>
      </button>

      {/* Dropdown Popover */}
      {isOpen && (
        <div
          className={cn(
            'absolute left-0 sm:left-auto sm:right-0 top-full z-50 mt-1.5 w-[360px] sm:w-[460px] max-w-[calc(100vw-2rem)] rounded-md border border-border bg-surface shadow-lg',
            'animate-in fade-in-0 zoom-in-95 duration-100 flex flex-col overflow-hidden',
          )}
        >
          {/* Popover Header: Search & Filter Chips */}
          <div className="border-b border-border p-3 space-y-2.5 bg-surface">
            {/* Search Input */}
            <div className="relative">
              <MagnifyingGlass
                className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted pointer-events-none"
                aria-hidden="true"
              />
              <input
                ref={searchInputRef}
                id={searchInputId}
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setHighlightedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                placeholder="Search by title or course code…"
                aria-label="Search modules by title or course code"
                aria-controls={listboxId}
                aria-autocomplete="list"
                aria-activedescendant={
                  filteredItems[safeHighlightedIndex]
                    ? `${id}-opt-${filteredItems[safeHighlightedIndex].document_id}`
                    : undefined
                }
                className="h-8 w-full rounded-sm border border-border bg-surface pl-8 pr-7 text-xs text-text placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    setHighlightedIndex(0);
                    searchInputRef.current?.focus();
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text cursor-pointer p-0.5"
                  aria-label="Clear search"
                >
                  <X className="size-3" aria-hidden="true" />
                </button>
              )}
            </div>

            {/* Filter Chips: All, Pending Review, Completed */}
            <div className="flex items-center gap-1.5" role="tablist" aria-label="Filter queue modules">
              <button
                type="button"
                role="tab"
                aria-selected={activeFilter === 'all'}
                onClick={() => {
                  setActiveFilter('all');
                  setHighlightedIndex(0);
                }}
                className={cn(
                  'px-2 py-1 rounded-full text-[11px] font-semibold transition-colors cursor-pointer flex items-center gap-1',
                  activeFilter === 'all'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-surface-subtle text-text-muted hover:text-text border border-border',
                )}
              >
                <span>All</span>
                <span className="text-[10px] opacity-80">({counts.all})</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeFilter === 'pending'}
                onClick={() => {
                  setActiveFilter('pending');
                  setHighlightedIndex(0);
                }}
                className={cn(
                  'px-2 py-1 rounded-full text-[11px] font-semibold transition-colors cursor-pointer flex items-center gap-1',
                  activeFilter === 'pending'
                    ? 'bg-warning text-warning-foreground shadow-xs'
                    : 'bg-surface-subtle text-text-muted hover:text-text border border-border',
                )}
              >
                <span>Pending Review</span>
                <span className="text-[10px] opacity-80">({counts.pending})</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeFilter === 'completed'}
                onClick={() => {
                  setActiveFilter('completed');
                  setHighlightedIndex(0);
                }}
                className={cn(
                  'px-2 py-1 rounded-full text-[11px] font-semibold transition-colors cursor-pointer flex items-center gap-1',
                  activeFilter === 'completed'
                    ? 'bg-success text-success-foreground shadow-xs'
                    : 'bg-surface-subtle text-text-muted hover:text-text border border-border',
                )}
              >
                <span>Completed</span>
                <span className="text-[10px] opacity-80">({counts.completed})</span>
              </button>
            </div>
          </div>

          {/* Module List */}
          <div
            id={listboxId}
            role="listbox"
            aria-label="Module queue"
            className="max-h-72 overflow-y-auto divide-y divide-border/60 bg-surface"
          >
            {isLoadingQueue && !propItems && allItems.length === 0 ? (
              <div className="p-6 text-center text-xs text-text-muted flex items-center justify-center gap-2">
                <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
                <span>Loading queue modules…</span>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="p-6 text-center space-y-1">
                <p className="text-xs font-semibold text-text">No modules match criteria</p>
                <p className="text-[11px] text-text-muted">
                  {searchQuery
                    ? `No modules matching "${searchQuery}"`
                    : 'No modules found in this category'}
                </p>
              </div>
            ) : (
              filteredItems.map((item, index) => {
                const isSelected = item.document_id === selectedDocumentId;
                const isHighlighted = index === safeHighlightedIndex;
                const optId = `${id}-opt-${item.document_id}`;

                return (
                  <button
                    key={item.document_id}
                    id={optId}
                    ref={(el) => {
                      itemRefs.current[index] = el;
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(item.document_id)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'w-full text-left p-3 transition-colors cursor-pointer flex flex-col gap-2',
                      isHighlighted ? 'bg-surface-subtle' : 'hover:bg-surface-subtle',
                      isSelected && 'border-l-2 border-primary bg-primary/5',
                    )}
                  >
                    {/* Row 1: Course Code, Title & Selection Check */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0 flex-1">
                        {item.course_code && (
                          <span className="shrink-0 font-mono text-[11px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-xs border border-primary/20">
                            {item.course_code}
                          </span>
                        )}
                        <span className="truncate text-xs font-bold text-text" title={item.title}>
                          {item.title}
                        </span>
                      </div>
                      {isSelected && (
                        <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" aria-hidden="true" />
                      )}
                    </div>

                    {/* Row 2: Metadata (Program, Date) & My Desk Status Badge */}
                    <div className="flex items-center justify-between gap-2 text-[11px] text-text-muted">
                      <div className="flex items-center gap-2">
                        {item.program && (
                          <span className="font-semibold text-text-muted uppercase">
                            {item.program}
                          </span>
                        )}
                        {item.uploaded_at && (
                          <span className="text-text-muted/70">
                            Uploaded {formatUploadDate(item.uploaded_at)}
                          </span>
                        )}
                      </div>
                      <DeskStatusBadge status={item.my_status} score={item.my_score} />
                    </div>

                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default SpecialistQueueSwitcher;
