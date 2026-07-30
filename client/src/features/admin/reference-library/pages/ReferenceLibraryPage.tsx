import { useState } from 'react';
import { BookOpen, Scale } from 'lucide-react';
import { LibraryTabButton, PageHeader } from '../components/PageHeader';
import { PolicyLibraryTab } from '../components/PolicyLibraryTab';
import { ReferenceLibraryTab } from '../components/ReferenceLibraryTab';

type LibraryTab = 'references' | 'policies';

export function ReferenceLibraryPage() {
  const [activeTab, setActiveTab] = useState<LibraryTab>('references');

  return (
    <section className="grid gap-5">
      <PageHeader />
      <div
        role="tablist"
        aria-label="Reference library sections"
        className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-1"
      >
        <LibraryTabButton
          id="library-tab-references"
          isActive={activeTab === 'references'}
          onSelect={() => setActiveTab('references')}
          label="References"
          icon={BookOpen}
        />
        <LibraryTabButton
          id="library-tab-policies"
          isActive={activeTab === 'policies'}
          onSelect={() => setActiveTab('policies')}
          label="Policies"
          icon={Scale}
        />
      </div>
      {activeTab === 'references' ? <ReferenceLibraryTab /> : <PolicyLibraryTab />}
    </section>
  );
}
