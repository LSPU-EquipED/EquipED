import { cn } from '@/shared/components/utils';

type DocumentType = 'slm' | 'syllabus' | 'curriculum' | 'reference';

interface DocumentTypeSelectorProps {
  value?: DocumentType;
  onChange?: (type: DocumentType) => void;
}

const DOCUMENT_TYPES: Array<{ id: DocumentType; label: string; description: string }> = [
  { id: 'slm', label: 'Student Learning Module', description: 'SLM evaluation materials' },
  { id: 'syllabus', label: 'Syllabus', description: 'Course syllabus documents' },
  { id: 'curriculum', label: 'Curriculum', description: 'Curriculum materials' },
  { id: 'reference', label: 'Reference', description: 'Reference documents' },
];

export function DocumentTypeSelector({ value = 'slm', onChange }: DocumentTypeSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold text-text mb-1.5 block">
        Document type
      </label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.id}
            type="button"
            onClick={() => onChange?.(type.id)}
            className={cn(
              'rounded-sm border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              value === type.id
                ? 'border-primary bg-primary-soft text-text'
                : 'border-border bg-surface hover:border-border hover:bg-surface-subtle text-text',
            )}
          >
            <div className={cn('text-xs font-semibold', value === type.id ? 'text-primary' : 'text-text')}>
              {type.label}
            </div>
            <div className="text-[11px] text-text-muted mt-1 leading-snug">
              {type.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
