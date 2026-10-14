import { FileText, MagnifyingGlass } from '@phosphor-icons/react';
import { ActionsMenu, type MenuAction } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';

interface DocumentActionsMenuProps {
  document: ClientDocument;
  onInspect?: (document: ClientDocument) => void;
}

export function DocumentActionsMenu({ document, onInspect }: DocumentActionsMenuProps) {
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
  ];

  return <ActionsMenu name={document.title} actions={actions} />;
}
