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
      <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 block">
        Document Type
      </label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type.id}
            type="button"
            onClick={() => onChange?.(type.id)}
            className={`rounded-sm border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-[#1b3b87] ${
              value === type.id
                ? 'border-[#1b3b87] bg-[#1b3b87]/10 text-[#1b3b87]'
                : 'border-slate-200 bg-transparent hover:border-slate-300 hover:bg-slate-50 text-slate-600'
            }`}
          >
            <div className="font-bold text-xs uppercase tracking-wider">{type.label}</div>
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mt-1">
              {type.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
