// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdapterRow } from '../AdapterRow';

const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>
);

afterEach(cleanup);
it('keeps adapter provenance accessible from the version row', () => {
  render(
    wrap(<table>
      <tbody>
        <AdapterRow
          onPublish={vi.fn()}
          onUnpublish={vi.fn()}
          adapter={{
            gguf_filename: 'sme-v2.gguf',
            loaded: true,
            published: false,
            adapter_id: 'adapter-1',
            agent_id: 'sme',
            job_id: 'source-job',
            version: 2,
            file_sha256: 'full-file-hash',
            size_bytes: 1048576,
            created_at: '2026-09-29T00:00:00Z',
          }}
        />
      </tbody>
    </table>),
  );
  expect(screen.getByText('v2')).toBeDefined();
  expect(screen.getByText('1.0 MB')).toBeDefined();
  const toggle = screen.getByRole('button', { name: /show details for fine-tuned model v2/i });
  fireEvent.click(toggle);
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  expect(screen.getByText('source-job')).toBeDefined();
  expect(screen.getByText('full-file-hash')).toBeDefined();
});

const base = {
  gguf_filename: 'sme-v7.gguf',
  loaded: true,
  published: false,
  adapter_id: 'adapter-7',
  agent_id: 'sme',
  job_id: 'source-job-7',
  version: 7,
  file_sha256: 'hash-7',
  size_bytes: 1048576,
  created_at: '2026-10-03T00:00:00Z',
};

function renderRow(adapter: typeof base & { training_summary?: unknown }) {
  return render(
    wrap(<table>
      <tbody>
        <AdapterRow
          onPublish={vi.fn()}
          onUnpublish={vi.fn()}
          adapter={adapter as never}
        />
      </tbody>
    </table>),
  );
}

it('shows the training summary above a collapsed IT-staff section', () => {
  renderRow({
    ...base,
    training_summary: { version: 1, steps: 12, last: { step: 12, margin: 1.4 } },
  });
  fireEvent.click(screen.getByRole('button', { name: /show details for fine-tuned model v7/i }));
  expect(screen.getByText('1.40')).toBeDefined();
  const technical = screen.getByText('For IT staff');
  expect(technical.closest('details')?.hasAttribute('open')).toBe(false);
  expect(screen.getByText('sme-v7.gguf')).toBeDefined();
  expect(screen.getByText('source-job-7')).toBeDefined();
});

it('shows "Not recorded" for adapters without a training summary', () => {
  renderRow(base);
  fireEvent.click(screen.getByRole('button', { name: /show details for fine-tuned model v7/i }));
  expect(screen.getByText('Not recorded')).toBeDefined();
});

it('renders the GGUF panel inside the details area', () => {
  renderRow({ ...base, gguf: null } as never);
  fireEvent.click(screen.getByRole('button', { name: /show details for fine-tuned model v7/i }));
  expect(screen.getByText('GGUF file')).toBeDefined();
  expect(screen.getByText('Not uploaded')).toBeDefined();
});
