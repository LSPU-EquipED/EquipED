import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';

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
    <div className="border border-slate-200 bg-white rounded-sm">
      <div className="border-b border-slate-200 p-4 bg-slate-50/50">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
          Link Reference Documents
        </h3>
        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider mt-0.5">
          Associate reference materials with this evaluation
        </p>
      </div>
      <div className="p-4">
        <div className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="search-refs"
              className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 block"
            >
              Search references
            </label>
            <input
              type="text"
              id="search-refs"
              placeholder="Search by document name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
            />
          </div>

          {filteredReferences.length > 0 ? (
            <div className="space-y-1 max-h-64 overflow-y-auto rounded-sm border border-slate-200 p-2">
              {filteredReferences.map((ref) => (
                <label
                  key={ref.id}
                  className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-sm cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedRefs.includes(ref.id)}
                    onChange={() => handleToggleReference(ref.id)}
                    className="size-4 rounded-sm border-slate-300 text-[#1b3b87] focus:ring-2 focus:ring-[#1b3b87] accent-[#1b3b87]"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-slate-800 truncate">{ref.name}</div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mt-0.5">
                      {ref.uploadedAt}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          ) : (
            <div className="rounded-sm border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                No reference documents available
              </p>
            </div>
          )}

          <div className="border-t border-slate-200 my-4" />

          {selectedRefs.length > 0 && (
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              {selectedRefs.length} document{selectedRefs.length === 1 ? '' : 's'} selected
            </div>
          )}

          <button
            type="button"
            onClick={handleLink}
            disabled={selectedRefs.length === 0}
            className="w-full h-10 inline-flex items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Link Selected References
          </button>
        </div>
      </div>
    </div>
  );
}
