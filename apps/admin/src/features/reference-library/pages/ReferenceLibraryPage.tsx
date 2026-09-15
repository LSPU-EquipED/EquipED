import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Books, Scales, UploadSimple } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import { LibraryTabButton } from '../components/PageHeader';
import { PolicyLibraryTab } from '../components/PolicyLibraryTab';
import { ReferenceLibraryTab } from '../components/ReferenceLibraryTab';

type LibraryTab = 'references' | 'policies';

export function ReferenceLibraryPage() {
  const [activeTab, setActiveTab] = useState<LibraryTab>('references');

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
      {/* ── Section Segmented Toggle & Ingest Button Bar ─────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div
          role="tablist"
          aria-label="Reference library sections"
          className="inline-flex items-center gap-1 p-0.5 rounded-sm bg-surface-subtle border border-border"
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
        </div>

        <div>
          <Link
            to="/admin/ingest"
            className={cn(
              BUTTON_STYLES.base,
              BUTTON_STYLES.variants.primary,
              BUTTON_STYLES.sizes.md,
              'text-xs sm:text-sm font-semibold h-10 px-4',
            )}
          >
            <UploadSimple className="size-4 shrink-0" aria-hidden="true" />
            <span>Ingest Reference</span>
          </Link>
        </div>
      </div>

      {activeTab === 'references' ? <ReferenceLibraryTab /> : <PolicyLibraryTab />}
    </section>
  );
}
