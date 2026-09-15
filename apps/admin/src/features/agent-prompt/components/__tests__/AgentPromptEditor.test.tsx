// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AgentPromptEditor } from '../AgentPromptEditor';
import * as hooksModule from '../../hooks/usePromptVersions';
import type { PromptVersionListResponse } from '../../types';

const mockNavigate = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ agentId: 'sme' }),
}));

const mockVersionsData: PromptVersionListResponse = {
  agent_id: 'sme',
  versions: [
    {
      version_id: 'v-2',
      version_number: 2,
      prompt_text: 'You are the SME evaluator for LSPU SLM modules.',
      is_active: true,
      updated_by: 'admin-1',
      motivation: 'Updated syllabus guidelines',
      created_at: '2026-08-30T10:00:00Z',
    },
    {
      version_id: 'v-1',
      version_number: 1,
      prompt_text: 'Initial SME prompt directive.',
      is_active: false,
      updated_by: 'admin-1',
      motivation: 'Initial baseline',
      created_at: '2026-08-25T10:00:00Z',
    },
  ],
  total: 2,
};

describe('AgentPromptEditor', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderEditor() {
    return render(
      <QueryClientProvider client={queryClient}>
        <AgentPromptEditor />
      </QueryClientProvider>,
    );
  }

  it('renders agent tabs and displays active prompt directive for selected agent', () => {
    vi.spyOn(hooksModule, 'usePromptVersions').mockReturnValue({
      data: mockVersionsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePromptVersions>);

    renderEditor();

    // Tabs
    expect(screen.getByRole('tab', { name: /Program Coordinator/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Subject Matter Expert/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Gender & Development/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /Intellectual Property/i })).toBeDefined();

    // Active version badge and textarea placeholder
    expect(screen.getByText('v2 Active')).toBeDefined();
    expect(screen.getByLabelText(/Prompt Text/i)).toBeDefined();
    expect(screen.getByLabelText(/Update Motivation/i)).toBeDefined();

    // History card
    expect(screen.getByText('v1')).toBeDefined();
    expect(screen.getByText('Archived')).toBeDefined();
    expect(screen.getByRole('button', { name: /Revert/i })).toBeDefined();
  });

  it('switches agent tabs and navigates when clicked', () => {
    vi.spyOn(hooksModule, 'usePromptVersions').mockReturnValue({
      data: mockVersionsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePromptVersions>);

    renderEditor();

    const coordTab = screen.getByRole('tab', { name: /Program Coordinator/i });
    fireEvent.click(coordTab);

    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/admin/prompts/$agentId',
      params: { agentId: 'coordinator' },
    });
  });

  it('opens revert confirmation modal when clicking Revert on archived version', () => {
    vi.spyOn(hooksModule, 'usePromptVersions').mockReturnValue({
      data: mockVersionsData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooksModule.usePromptVersions>);

    renderEditor();

    const revertBtn = screen.getByRole('button', { name: /Revert/i });
    fireEvent.click(revertBtn);

    // Modal opens
    expect(screen.getByRole('dialog')).toBeDefined();
    expect(screen.getByText(/Revert Prompt to v1/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Confirm Revert to v1/i })).toBeDefined();
  });
});
