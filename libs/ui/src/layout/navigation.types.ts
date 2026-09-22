import type { Icon } from '@phosphor-icons/react';

export interface NavItem {
  to: string;
  label: string;
  icon: Icon;
  exact: boolean;
}

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: readonly NavItem[];
}
