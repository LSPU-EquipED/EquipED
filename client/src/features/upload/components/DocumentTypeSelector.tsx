import { Label } from '@/shared/components/ui/label';

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
    <div className="space-y-3">
      <Label>Document Type</Label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.id}
            onClick={() => onChange?.(type.id)}
            className={`rounded-lg border-2 p-3 text-left transition-colors ${
              value === type.id
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border bg-transparent hover:border-primary/50 hover:bg-primary/5'
            }`}
          >
            <div className="font-medium text-sm">{type.label}</div>
            <div className="text-xs text-muted-foreground">{type.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
