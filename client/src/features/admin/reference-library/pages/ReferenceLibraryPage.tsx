import { useState } from 'react';
import { Books, Scales } from '@phosphor-icons/react';
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
        className="flex flex-wrap items-center gap-2 border-b border-border pb-1"
      >
        <LibraryTabButton
          id="library-tab-references"
          isActive={activeTab === 'references'}
          onSelect={() => setActiveTab('references')}
          label="References"
          icon={Books}
        />
        <LibraryTabButton
          id="library-tab-policies"
          isActive={activeTab === 'policies'}
          onSelect={() => setActiveTab('policies')}
          label="Policies"
          icon={Scales}
        />
      </div>
      {activeTab === 'references' ? <ReferenceLibraryTab /> : <PolicyLibraryTab />}
    </section>
  );
}
