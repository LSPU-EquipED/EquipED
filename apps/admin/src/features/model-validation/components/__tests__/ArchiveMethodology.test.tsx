// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import archive from '../../../../../../server/modules/admin/data/fine_tuning_results.json';
import type { ArchivedExperiment } from '../../archiveTypes';
import { presentArchiveLimitation } from '../../utils/archiveMethodology';
import { ArchiveMethodology } from '../ArchiveMethodology';

afterEach(cleanup);
const experiment = archive.experiments.find((e) => e.id === 'v9') as ArchivedExperiment;

describe('ArchiveMethodology', () => {
  it('distinguishes repeated comparisons from unique SLMs and missing dataset counts', () => {
    render(<ArchiveMethodology experiment={experiment} archivedOn={archive.archived_on} />);
    const facts = screen.getByRole('region', { name: 'Dataset facts' });
    const value = (label: string) =>
      within(facts).getByText(label).parentElement?.querySelector('dd')?.textContent;
    expect(value('Comparisons')).toBe('4');
    expect(value('Unique SLMs')).toBe('3');
    expect(value('Dataset pairs')).toBe('Not recorded');
    expect(value('Reference scores')).toBe('Synthetic');
    const limits = screen.getByRole('region', { name: 'Study limitations' });
    expect(within(limits).getByText('Repeated input:')).toBeDefined();
    expect(within(limits).getByText('Held-out status:')).toBeDefined();
    expect(within(limits).getAllByRole('listitem')).toHaveLength(experiment.limitations.length);
    expect(limits.closest('details')).toBeNull();
  });

  it('keeps archive dates, identifiers and hashes together in a default-closed disclosure', () => {
    const source = archive.experiments.find((e) => e.id === 'gad-v5')! as ArchivedExperiment;
    render(<ArchiveMethodology experiment={source} archivedOn={archive.archived_on} />);
    const toggle = screen.getByText('Provenance');
    const details = toggle.closest('details')!;
    expect(details.open).toBe(false);
    expect(screen.getByText(archive.archived_on).closest('details')).toBe(details);
    expect(screen.getByText(source.runs[0].base_validation_id).closest('details')).toBe(details);
    expect(screen.getByText(source.runs[0].adapter_evaluation_id).closest('details')).toBe(details);
    expect(screen.getAllByText(source.runs[0].prompt_hashes[0].sha256)[0].closest('details')).toBe(
      details,
    );
    expect(details.querySelector('details')).toBeNull();
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
  });

  it('does not infer missing source counts or discard unfamiliar limitations', () => {
    const legacy: ArchivedExperiment = {
      ...experiment,
      unique_slm_count: undefined,
      limitations: ['An additional study constraint remains important.'],
    };
    render(<ArchiveMethodology experiment={legacy} archivedOn={archive.archived_on} />);
    expect(screen.getByText('Unique SLMs').parentElement?.querySelector('dd')?.textContent).toBe(
      'Not recorded',
    );
    expect(screen.getByText('Study limitation:')).toBeDefined();
    expect(screen.getByText('An additional study constraint remains important.')).toBeDefined();
  });

  it('provides edited copy for each archived limitation without changing its source', () => {
    for (const entry of archive.experiments) {
      for (const note of entry.limitations) {
        const display = presentArchiveLimitation(note);
        expect(display.label).not.toBe('Study limitation');
        expect(display.text.length).toBeGreaterThan(0);
      }
    }
  });
});
