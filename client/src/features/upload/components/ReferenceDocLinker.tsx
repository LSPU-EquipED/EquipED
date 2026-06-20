import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Separator } from '@/shared/components/ui/separator';
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
    <Card>
      <CardHeader>
        <CardTitle>Link Reference Documents</CardTitle>
        <CardDescription>Associate reference materials with this evaluation</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="search-refs">Search references</Label>
            <Input
              id="search-refs"
              placeholder="Search by document name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {filteredReferences.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto rounded-lg border border-border p-3">
              {filteredReferences.map((ref) => (
                <label
                  key={ref.id}
                  className="flex items-center gap-3 p-2 hover:bg-muted rounded-md cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedRefs.includes(ref.id)}
                    onChange={() => handleToggleReference(ref.id)}
                    className="rounded border-input"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{ref.name}</div>
                    <div className="text-xs text-muted-foreground">{ref.uploadedAt}</div>
                  </div>
                </label>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border bg-muted/50 p-6 text-center">
              <p className="text-sm text-muted-foreground">No reference documents available</p>
            </div>
          )}

          <Separator />

          {selectedRefs.length > 0 && (
            <div className="text-sm text-muted-foreground">
              {selectedRefs.length} document{selectedRefs.length === 1 ? '' : 's'} selected
            </div>
          )}

          <Button onClick={handleLink} disabled={selectedRefs.length === 0} className="w-full">
            Link Selected References
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
