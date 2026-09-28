// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AgentPromptPage } from '../AgentPromptPage';
import * as hooksModule from '../../hooks/usePromptVersions';
import type { PromptVersionListResponse } from '../../types';

const router = vi.hoisted(() => ({ agentId: 'sme', navigate: vi.fn() }));
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => router.navigate,
  useParams: () => ({ agentId: router.agentId }),
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
const activeText = mockVersionsData.versions[0].prompt_text;
const savePrompt = vi.fn();
const restorePrompt = vi.fn();
const refetch = vi.fn();

function mockHistory(overrides = {}) {
  vi.spyOn(hooksModule, 'usePromptVersions').mockReturnValue({
    data: mockVersionsData,
    isLoading: false,
    isError: false,
    refetch,
    ...overrides,
  } as unknown as ReturnType<typeof hooksModule.usePromptVersions>);
}
function input() {
  return screen.getByRole('textbox', { name: /Prompt text/ }) as HTMLTextAreaElement;
}
function saveButton() {
  return screen.getByRole('button', { name: 'Save new revision' }) as HTMLButtonElement;
}

beforeEach(() => {
  router.agentId = 'sme';
  vi.clearAllMocks();
  savePrompt.mockResolvedValue(mockVersionsData.versions[0]);
  restorePrompt.mockResolvedValue(mockVersionsData.versions[0]);
  mockHistory();
  vi.spyOn(hooksModule, 'useCreatePrompt').mockReturnValue({
    mutateAsync: savePrompt,
    reset: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof hooksModule.useCreatePrompt>);
  vi.spyOn(hooksModule, 'useRevertPrompt').mockReturnValue({
    mutateAsync: restorePrompt,
    reset: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof hooksModule.useRevertPrompt>);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AgentPromptPage', () => {
  it('loads the active prompt as editable content and prevents unchanged publication', () => {
    render(<AgentPromptPage />);
    expect(input().value).toBe(activeText);
    expect(input().placeholder).not.toBe(activeText);
    expect(saveButton().disabled).toBe(true);
    expect(
      screen.getByRole('tab', { name: 'Subject Matter Expert', selected: true }),
    ).toBeDefined();
    expect(screen.getByRole('tabpanel', { name: 'Subject Matter Expert' })).toBeDefined();
    expect(screen.getAllByText('Active')).toHaveLength(1);
    expect(screen.queryByText('Archived')).toBeNull();
  });

  it('navigates by tab click and arrow, Home, and End keys', () => {
    render(<AgentPromptPage />);
    fireEvent.click(screen.getByRole('tab', { name: 'Program Coordinator' }));
    expect(router.navigate).toHaveBeenLastCalledWith({
      to: '/admin/prompts/$agentId',
      params: { agentId: 'coordinator' },
    });
    const sme = screen.getByRole('tab', { name: 'Subject Matter Expert' });
    fireEvent.keyDown(sme, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: /Gender & Development/ }));
    expect(router.navigate).toHaveBeenLastCalledWith({
      to: '/admin/prompts/$agentId',
      params: { agentId: 'gad' },
    });
    fireEvent.keyDown(sme, { key: 'Home' });
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Program Coordinator' }));
    fireEvent.keyDown(sme, { key: 'End' });
    const itso = screen.getByRole('tab', { name: 'Innovation and Technology Support Office' });
    expect(document.activeElement).toBe(itso);
    fireEvent.keyDown(itso, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Program Coordinator' }));
  });

  it('restores the active text and clears the change note when discarding', () => {
    render(<AgentPromptPage />);
    fireEvent.change(input(), { target: { value: 'Edited prompt' } });
    fireEvent.change(screen.getByLabelText(/Change note/), { target: { value: 'A reason' } });
    expect(saveButton().disabled).toBe(false);
    expect(screen.getByText('Unsaved changes')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    expect(input().value).toBe(activeText);
    expect((screen.getByLabelText(/Change note/) as HTMLInputElement).value).toBe('');
    expect(saveButton().disabled).toBe(true);
  });

  it('keeps a cleared draft empty instead of falling back to active content', () => {
    render(<AgentPromptPage />);
    fireEvent.change(input(), { target: { value: '' } });
    expect(input().value).toBe('');
    expect(screen.getByText('0 characters · 0 lines')).toBeDefined();
    expect(saveButton().disabled).toBe(true);
    expect(
      (screen.getByRole('button', { name: 'Copy prompt' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('loads an archived version as a draft and only publishes when explicitly saved', async () => {
    render(<AgentPromptPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Use version 1 as draft' }));
    expect(input().value).toBe(mockVersionsData.versions[1].prompt_text);
    expect(savePrompt).not.toHaveBeenCalled();
    expect(restorePrompt).not.toHaveBeenCalled();
    fireEvent.click(saveButton());
    await waitFor(() =>
      expect(savePrompt).toHaveBeenCalledWith({
        prompt_text: mockVersionsData.versions[1].prompt_text,
        motivation: 'Derived from v1',
      }),
    );
  });

  it('preserves the draft when saving fails', async () => {
    savePrompt.mockRejectedValueOnce(new Error('Save failed'));
    render(<AgentPromptPage />);
    fireEvent.change(input(), { target: { value: 'Keep this draft' } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(savePrompt).toHaveBeenCalled());
    expect(input().value).toBe('Keep this draft');
  });

  it('copies the actual draft and reports a clipboard failure without a success message', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Clipboard unavailable'));
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    render(<AgentPromptPage />);
    fireEvent.change(input(), { target: { value: 'Copy this draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Copy prompt' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Could not copy'));
    expect(writeText).toHaveBeenCalledWith('Copy this draft');
    expect(screen.queryByRole('button', { name: 'Copied' })).toBeNull();
  });

  it('requires confirmation to restore and keeps the dialog open on failure', async () => {
    restorePrompt.mockRejectedValueOnce(new Error('Restore failed'));
    render(<AgentPromptPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Restore version 1' }));
    const dialog = screen.getByRole('dialog', { name: 'Restore version 1?' });
    expect(restorePrompt).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Restore version' }));
    await waitFor(() => expect(within(dialog).getByRole('alert')).toBeDefined());
    expect(restorePrompt).toHaveBeenCalledWith('v-1');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Restore version' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('clears the previous agent draft and restore dialog when the route changes', () => {
    const { rerender } = render(<AgentPromptPage />);
    fireEvent.change(input(), { target: { value: 'SME draft only' } });
    fireEvent.click(screen.getByRole('button', { name: 'Restore version 1' }));
    router.agentId = 'gad';
    mockHistory({
      data: {
        ...mockVersionsData,
        agent_id: 'gad',
        versions: [{ ...mockVersionsData.versions[0], prompt_text: 'GAD instructions' }],
      },
    });
    rerender(<AgentPromptPage />);
    expect(input().value).toBe('GAD instructions');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows a loading skeleton and a retry action on retrieval failure', () => {
    mockHistory({ data: undefined, isLoading: true });
    const { rerender } = render(<AgentPromptPage />);
    expect(screen.getByRole('status', { name: 'Loading system prompt' })).toBeDefined();
    expect(screen.queryByRole('textbox')).toBeNull();
    mockHistory({ data: undefined, isLoading: false, isError: true });
    rerender(<AgentPromptPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(refetch).toHaveBeenCalledOnce();
  });

  it('allows the first prompt to be authored when there is no active version', () => {
    mockHistory({ data: { ...mockVersionsData, versions: [], total: 0 } });
    render(<AgentPromptPage />);
    expect(input().value).toBe('');
    expect(screen.getByText('No revisions yet')).toBeDefined();
    fireEvent.change(input(), { target: { value: 'First prompt' } });
    expect(saveButton().disabled).toBe(false);
  });
});
