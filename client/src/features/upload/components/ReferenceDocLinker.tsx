import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import { Button } from '@/shared/components/Button';
import { Input } from '@/shared/components/Input';

interface LinkedReference {
  id: string;
  name: string;
  uploadedAt: string;
}

interface ReferenceDocLinkerProps {
  evaluationId?: string;
  onLink?: (refIds: string[]) => void;
}

export function ReferenceDocLinker({ onLink }: ReferenceDocLinkerProps) {
  const [selectedRefs, setSelectedRefs] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const { data } = useQuery({
    queryKey: ['reference-documents'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'REFERENCE' }),
  });

  const availableReferences: LinkedReference[] = (data?.items ?? []).map((doc) => ({
    id: doc.documentId,
    name: doc.title,
    uploadedAt: new Date(doc.uploadedAt).toLocaleDateString(),
  }));

  const filteredReferences = availableReferences.filter((ref) =>
    ref.name.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const handleToggleReference = (refId: string) => {
    setSelectedRefs((prev) =>
      prev.includes(refId) ? prev.filter((id) => id !== refId) : [...prev, refId],
    );
  };

  const handleLink = () => {
    onLink?.(selectedRefs);
    setSelectedRefs([]);
  };

  return (
    <div className="border border-border bg-surface rounded-sm overflow-hidden">
      <div className="border-b border-border p-4 bg-surface-subtle">
        <h3 className="text-sm font-semibold text-text">
          Link reference documents
        </h3>
        <p className="text-xs text-text-muted font-medium mt-0.5">
          Associate reference materials with this evaluation
        </p>
      </div>
      <div className="p-4">
        <div className="space-y-4">
          <Input
            type="text"
            id="search-refs"
            label="Search references"
            placeholder="Search by document name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />

          {filteredReferences.length > 0 ? (
            <div className="space-y-1 max-h-64 overflow-y-auto rounded-sm border border-border p-2 bg-surface">
              {filteredReferences.map((ref) => (
                <label
                  key={ref.id}
                  className="flex items-center gap-3 p-2 hover:bg-surface-subtle rounded-sm cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedRefs.includes(ref.id)}
                    onChange={() => handleToggleReference(ref.id)}
                    className="size-4 rounded-xs border-input text-primary focus:ring-2 focus:ring-ring accent-primary"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold text-text truncate">{ref.name}</div>
                    <div className="text-[10px] text-text-muted font-medium mt-0.5">
                      {ref.uploadedAt}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          ) : (
            <div className="rounded-sm border border-dashed border-border bg-surface-subtle/50 p-6 text-center">
              <p className="text-xs font-medium text-text-muted">
                No reference documents available
              </p>
            </div>
          )}

          <div className="border-t border-border my-4" />

          {selectedRefs.length > 0 && (
            <div className="text-xs font-medium text-text-muted">
              {selectedRefs.length} document{selectedRefs.length === 1 ? '' : 's'} selected
            </div>
          )}

          <Button
            type="button"
            variant="primary"
            onClick={handleLink}
            disabled={selectedRefs.length === 0}
            className="w-full uppercase tracking-wider text-xs font-semibold"
          >
            Link Selected References
          </Button>
        </div>
      </div>
    </div>
  );
}
