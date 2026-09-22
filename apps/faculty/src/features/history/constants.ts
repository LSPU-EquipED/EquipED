import type { TargetAgent } from '@equiped/types';

export interface HistoryRoleTab {
  id: TargetAgent;
  label: string;
}

export const HISTORY_ROLE_TABS: readonly HistoryRoleTab[] = [
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'gad', label: 'Gender & Development' },
  { id: 'itso', label: 'Innovation and Technology Support Office' },
];
