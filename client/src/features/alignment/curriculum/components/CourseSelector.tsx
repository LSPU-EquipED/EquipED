// Adapted from shared/components/ProgramSelector.tsx: same combobox
// mechanics (search, keyboard nav, ARIA), backed by courses instead of
// programs, with a flat (ungrouped) list since courses aren't organized
// into colleges the way programs are.
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import type { Course } from '../types';

type CourseSelectorProps = {
  value: string;
  onChange: (courseId: string) => void;
  courses: Course[];
  label?: string;
  placeholder?: string;
  hint?: string;
  id?: string;
  required?: boolean;
  disabled?: boolean;
};

export function CourseSelector({
  value,
  onChange,
  courses,
  label,
  placeholder = 'Select a course',
  hint,
  id: idProp,
  required,
  disabled,
}: CourseSelectorProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listId = `${id}-list`;

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const filteredCourses = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return courses;
    return courses.filter(
      (course) =>
        course.course_code.toLowerCase().includes(trimmed) ||
        course.course_title.toLowerCase().includes(trimmed),
    );
  }, [courses, query]);

  const selectedCourse = useMemo(
    () => courses.find((course) => course.course_id === value) ?? null,
    [courses, value],
  );

  const safeHighlightedIndex = Math.min(highlightedIndex, Math.max(0, filteredCourses.length - 1));

  const openPicker = () => {
    setIsOpen(true);
    setQuery('');
    const selectedIndex = courses.findIndex((course) => course.course_id === value);
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

  const handleSelect = (courseId: string) => {
    onChange(courseId);
    closePicker();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    const count = filteredCourses.length;
    if (count === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % count);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + count) % count);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const course = filteredCourses[safeHighlightedIndex];
      if (course) handleSelect(course.course_id);
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
    <div ref={containerRef} className="relative min-w-0 w-full">
      {label ? (
        <label
          htmlFor={id}
          className="mb-1.5 block text-xs font-semibold text-text"
        >
          {label}
          {required ? <span className="ml-1 text-destructive">*</span> : null}
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
          'flex h-10 min-w-0 w-full items-center justify-between gap-2 rounded-sm border border-input bg-surface px-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {selectedCourse ? (
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="text-sm font-bold text-text">{selectedCourse.course_code}</span>
            <span className="truncate text-sm font-medium text-text-muted">
              {selectedCourse.course_title}
            </span>
          </span>
        ) : (
          <span className="min-w-0 truncate text-sm font-medium text-text-muted">
            {placeholder}
          </span>
        )}
        <ChevronDown
          className={cn('size-4 shrink-0 text-text-muted transition-transform', isOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {isOpen ? (
        <div
          id={listId}
          role="listbox"
          aria-label={label ?? 'Courses'}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-hidden rounded-sm border border-border bg-surface shadow-sm"
        >
          <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-surface px-3 py-2">
            <Search className="size-4 text-text-muted" aria-hidden="true" />
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setHighlightedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search by code or course title"
              className="min-w-0 flex-1 bg-transparent text-sm font-semibold text-text placeholder:text-text-muted focus:outline-none"
              aria-autocomplete="list"
              aria-controls={listId}
            />
          </div>

          <div className="max-h-64 overflow-y-auto">
            {filteredCourses.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm font-medium text-text-muted">
                No courses found
              </div>
            ) : (
              filteredCourses.map((course, index) => {
                const isSelected = course.course_id === value;
                const isHighlighted = index === safeHighlightedIndex;
                return (
                  <button
                    key={course.course_id}
                    ref={(el) => {
                      itemRefs.current[index] = el;
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(course.course_id)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors focus:outline-none',
                      isHighlighted ? 'bg-primary-soft text-primary' : 'bg-surface hover:bg-surface-subtle text-text',
                      isSelected && 'bg-primary-soft font-semibold text-primary',
                    )}
                  >
                    <span className="flex min-w-0 flex-1 items-baseline gap-2">
                      <span className="text-sm font-bold">{course.course_code}</span>
                      <span className="truncate text-sm font-medium opacity-80">
                        {course.course_title}
                      </span>
                    </span>
                    {isSelected ? <Check className="size-4 shrink-0 text-primary" aria-hidden="true" /> : null}
                  </button>
                );
              })
            )}
          </div>
        </div>
      ) : null}

      {hint ? <p className="mt-1.5 text-xs font-normal text-text-muted">{hint}</p> : null}
    </div>
  );
}
