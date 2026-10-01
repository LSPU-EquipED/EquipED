import { ArrowRight, FileText, MagnifyingGlass } from '@phosphor-icons/react';
import { ActionsMenu, type MenuAction } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';
import type { SlmDisplayStatus } from '@/shared/utils/slmDisplayStatus';

interface DocumentActionsMenuProps {
  document: ClientDocument;
  display: Pick<SlmDisplayStatus, 'isClickable' | 'actionUrl' | 'actionLabel' | 'ariaLabel'>;
  onInspect?: (document: ClientDocument) => void;
}

export function DocumentActionsMenu({ document, display, onInspect }: DocumentActionsMenuProps) {
  const actions: MenuAction[] = [
    ...(onInspect
      ? [
          {
            label: 'View details',
            icon: <MagnifyingGlass className="size-4" />,
            onSelect: () => onInspect(document),
          },
        ]
      : []),
    {
      label: 'Open PDF',
      ariaLabel: `Open ${document.title} PDF`,
      icon: <FileText className="size-4" />,
      href: `/api/v1/documents/${document.documentId}/file`,
      target: '_blank',
      rel: 'noopener noreferrer',
    },
    ...(display.isClickable && display.actionUrl
      ? [
          {
            label: display.actionLabel,
            ariaLabel: display.ariaLabel,
            icon: <ArrowRight className="size-4" />,
            to: display.actionUrl,
          },
        ]
      : []),
  ];

  return <ActionsMenu name={document.title} actions={actions} />;
}
