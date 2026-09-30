// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { AdapterRow } from '../AdapterRow';

afterEach(cleanup);
it('keeps adapter provenance accessible from the version row', () => {
  render(
    <table>
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
    </table>,
  );
  expect(screen.getByText('v2')).toBeDefined();
  expect(screen.getByText('1.0 MB')).toBeDefined();
  const toggle = screen.getByRole('button', { name: /show details for adapter v2/i });
  fireEvent.click(toggle);
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  expect(screen.getByText('source-job')).toBeDefined();
  expect(screen.getByText('full-file-hash')).toBeDefined();
});
