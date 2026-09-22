// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SelectModuleModal } from '../SelectModuleModal';
import type { DeskQueueItem } from '../../types';

const mockNavigate = vi.fn();
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
}));

describe('SelectModuleModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('includes FAILED status modules so they are selectable and retryable', async () => {
    const mockItems: DeskQueueItem[] = [
      {
        document_id: 'doc-failed-001',
        title: 'Algorithms Module (Failed Eval)',
        course_code: 'CS102',
        program: 'BSCS',
        uploaded_at: '2026-08-20T10:00:00Z',
        my_status: 'FAILED',
        my_score: null,
        my_adjectival: null,
        peer_completed_count: 0,
        peer_completed_desks: [],
      },
      {
        document_id: 'doc-completed-002',
        title: 'Completed Module',
        course_code: 'CS103',
        program: 'BSCS',
        uploaded_at: '2026-08-20T10:00:00Z',
        my_status: 'COMPLETED',
        my_score: 3.5,
        my_adjectival: 'Satisfactory',
        peer_completed_count: 1,
        peer_completed_desks: ['sme'],
      },
    ];

    render(
      <SelectModuleModal
        agentId="sme"
        items={mockItems}
        onClose={vi.fn()}
      />,
    );

    // Failed module should be displayed in the modal
    expect(screen.getByText('Algorithms Module (Failed Eval)')).toBeDefined();
    // Completed module should NOT be in the unevaluated / retryable selection list
    expect(screen.queryByText('Completed Module')).toBeNull();

    // Clicking the failed module selects it and routes to its desk workspace
    const failedBtn = screen.getByRole('button', {
      name: /Algorithms Module \(Failed Eval\)/i,
    });
    fireEvent.click(failedBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: '/specialists/$agentId/$documentId',
        params: { agentId: 'sme', documentId: 'doc-failed-001' },
      });
    });
  });
});
