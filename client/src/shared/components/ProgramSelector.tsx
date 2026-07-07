import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import type { ProgramCollegeGroup, ProgramEntry } from '@/shared/constants/programs';

type FlatProgram = ProgramEntry & {
  groupCode: string;
  groupCollege: string;
};

type ProgramSelectorProps = {
  value: string;
  onChange: (value: string) => void;
  groups: ProgramCollegeGroup[];
  label?: string;
  placeholder?: string;
  hint?: string;
  id?: string;
  required?: boolean;
  disabled?: boolean;
};

export function ProgramSelector({
  value,
  onChange,
  groups,
  label,
  placeholder = 'Select a program',
  hint,
  id: idProp,
  required,
  disabled,
}: ProgramSelectorProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listId = `${id}-list`;
  const searchId = `${id}-search`;

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const normalizedValue = value.trim().toUpperCase();

  const allPrograms = useMemo<FlatProgram[]>(() => {
    const list: FlatProgram[] = [];
    for (const group of groups) {
      for (const program of group.programs) {
        list.push({
          ...program,
          groupCode: group.code,
          groupCollege: group.college,
        });
      }
    }
    return list;
  }, [groups]);

  const filteredGroups = useMemo<ProgramCollegeGroup[]>(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return groups;

    return groups
      .map((group) => ({
        ...group,
        programs: group.programs.filter((program) => {
          const codeMatch = program.code.toLowerCase().includes(trimmed);
          const nameMatch = program.name.toLowerCase().includes(trimmed);
          return codeMatch || nameMatch;
        }),
      }))
      .filter((group) => group.programs.length > 0);
  }, [groups, query]);

  const filteredPrograms = useMemo<FlatProgram[]>(() => {
    const list: FlatProgram[] = [];
    for (const group of filteredGroups) {
      for (const program of group.programs) {
        list.push({
          ...program,
          groupCode: group.code,
          groupCollege: group.college,
        });
      }
    }
    return list;
  }, [filteredGroups]);

  const selectedProgram = useMemo(
    () => allPrograms.find((program) => program.code.toUpperCase() === normalizedValue) ?? null,
    [allPrograms, normalizedValue],
  );

  const safeHighlightedIndex = Math.min(highlightedIndex, Math.max(0, filteredPrograms.length - 1));

  const openPicker = () => {
    setIsOpen(true);
    setQuery('');
    const selectedIndex = allPrograms.findIndex(
      (program) => program.code.toUpperCase() === normalizedValue,
    );
    setHighlightedIndex(Math.max(0, selectedIndex));
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  };

  const closePicker = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!isOpen) return;

    const active = itemRefs.current[safeHighlightedIndex];
    active?.scrollIntoView({ block: 'nearest' });
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

  const handleSelect = (programCode: string) => {
    onChange(programCode.toUpperCase());
    closePicker();
  };

  const handleQueryChange = (nextQuery: string) => {
    setQuery(nextQuery);
    setHighlightedIndex(0);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    const count = filteredPrograms.length;
    if (count === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % count);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + count) % count);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const program = filteredPrograms[safeHighlightedIndex];
      if (program) {
        handleSelect(program.code);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closePicker();
    }
  };

  const handleTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPicker();
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      {label ? (
        <label
          htmlFor={id}
          className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500"
        >
          {label}
          {required ? <span className="ml-1 text-[#b91c1c]">*</span> : null}
        </label>
      ) : null}

      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listId : undefined}
        onClick={() => (isOpen ? closePicker() : openPicker())}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          'flex h-10 w-full items-center justify-between gap-2 rounded-sm border border-slate-200 bg-white px-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-[#1b3b87]',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {selectedProgram ? (
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="text-sm font-bold text-slate-900">{selectedProgram.code}</span>
            <span className="truncate text-sm font-medium text-slate-500">
              {selectedProgram.name}
            </span>
          </span>
        ) : (
          <span className="text-sm font-semibold text-slate-500">{placeholder}</span>
        )}
        <ChevronDown
          className={cn(
            'size-4 shrink-0 text-slate-500 transition-transform',
            isOpen && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>

      {isOpen ? (
        <div
          id={listId}
          role="listbox"
          aria-label={label ?? 'Programs'}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-hidden rounded-sm border border-slate-200 bg-white"
        >
          <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
            <Search className="size-4 text-slate-400" aria-hidden="true" />
            <input
              ref={searchInputRef}
              id={searchId}
              type="text"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search by code or program name"
              className="flex-1 bg-transparent text-sm font-semibold text-slate-800 placeholder:text-slate-500 focus:outline-none"
              aria-autocomplete="list"
              aria-controls={listId}
              aria-activedescendant={
                filteredPrograms[safeHighlightedIndex]
                  ? `${id}-option-${safeHighlightedIndex}`
                  : undefined
              }
            />
          </div>

          <div className="max-h-64 overflow-y-auto">
            {filteredGroups.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm font-semibold text-slate-500">
                No programs found
              </div>
            ) : (
              filteredGroups.map((group) => (
                <div key={group.code} role="group" aria-label={group.college}>
                  <div className="bg-slate-50 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    {group.college}
                  </div>
                  {group.programs.map((program) => {
                    const flatIndex = filteredPrograms.findIndex(
                      (p) => p.code === program.code && p.groupCode === group.code,
                    );
                    const isSelected = program.code.toUpperCase() === normalizedValue;
                    const isHighlighted = flatIndex === safeHighlightedIndex;

                    return (
                      <button
                        key={`${group.code}-${program.code}`}
                        ref={(el) => {
                          itemRefs.current[flatIndex] = el;
                        }}
                        id={`${id}-option-${flatIndex}`}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelect(program.code)}
                        onMouseEnter={() => setHighlightedIndex(flatIndex)}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors focus:outline-none',
                          isHighlighted ? 'bg-[#1b3b87]/5' : 'bg-white hover:bg-slate-50/60',
                          isSelected && 'bg-[#1b3b87]/5',
                        )}
                      >
                        <span className="flex min-w-0 flex-1 items-baseline gap-2">
                          <span className="text-sm font-bold text-slate-900">{program.code}</span>
                          <span className="truncate text-sm font-medium text-slate-500">
                            {program.name}
                          </span>
                        </span>
                        {isSelected ? (
                          <Check className="size-4 shrink-0 text-[#1b3b87]" aria-hidden="true" />
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}

      {hint ? <p className="mt-2 text-xs font-medium text-slate-500">{hint}</p> : null}
    </div>
  );
}
