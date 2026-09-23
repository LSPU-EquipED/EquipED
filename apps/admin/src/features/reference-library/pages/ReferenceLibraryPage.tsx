import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Books, Scales, UploadSimple } from '@phosphor-icons/react';
import { cn, BUTTON_STYLES, PageContainer } from '@equiped/ui';
import { LibraryTabButton } from '../components/PageHeader';
import { PolicyLibraryTab } from '../components/PolicyLibraryTab';
import { ReferenceLibraryTab } from '../components/ReferenceLibraryTab';

type LibraryTab = 'references' | 'policies';

export function ReferenceLibraryPage() {
  const [activeTab, setActiveTab] = useState<LibraryTab>('references');

  return (
    <PageContainer as="section" className="space-y-5">
      <div className="flex flex-col gap-2 border-b border-border sm:flex-row sm:items-end sm:justify-between">
        <nav
          role="tablist"
          aria-label="Reference library sections"
          className="flex items-center gap-6"
        >
          <LibraryTabButton
            id="library-tab-references"
            isActive={activeTab === 'references'}
            onSelect={() => setActiveTab('references')}
            label="Syllabi & Curricula"
            icon={Books}
          />
          <LibraryTabButton
            id="library-tab-policies"
            isActive={activeTab === 'policies'}
            onSelect={() => setActiveTab('policies')}
            label="Institutional Policies"
            icon={Scales}
          />
        </nav>
        <Link
          to="/admin/ingest"
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.primary,
            BUTTON_STYLES.sizes.md,
            'mb-2 h-9 shrink-0 px-3.5 text-sm font-semibold',
          )}
        >
          <UploadSimple className="size-4 shrink-0" aria-hidden="true" />
          <span>Ingest reference</span>
        </Link>
      </div>

      {activeTab === 'references' ? <ReferenceLibraryTab /> : <PolicyLibraryTab />}
    </PageContainer>
  );
}
