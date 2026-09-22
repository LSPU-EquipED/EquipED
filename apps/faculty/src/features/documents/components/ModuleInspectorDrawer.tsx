import { useEffect, useState } from 'react';
import { usePresence } from '@equiped/ui';
import type { ClientDocument, LatestEvaluationItem, TargetAgent } from '@equiped/types';
import {
  getSlmDisplayStatus,
  type SlmStatusQueryState,
} from '@/shared/utils/slmDisplayStatus';
import { getHumanReadableTitle } from '../utils/moduleInspector.utils';
import { useClipboardCopy } from '../hooks/useClipboardCopy';
import { ModuleInspectorDrawerContent } from './ModuleInspectorDrawerContent';

export interface ModuleInspectorDrawerProps {
  document: ClientDocument | null;
  latestEvaluation?: LatestEvaluationItem;
  latestEvalsState?: SlmStatusQueryState;
  targetAgent?: TargetAgent;
  onClose: () => void;
}

export function ModuleInspectorDrawer({
  document,
  latestEvaluation,
  latestEvalsState,
  targetAgent = 'sme',
  onClose,
}: ModuleInspectorDrawerProps) {
  const isOpen = Boolean(document);
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 240 });
  const [cachedDoc, setCachedDoc] = useState<ClientDocument | null>(document);
  const { copiedValue, copy } = useClipboardCopy({ resetTimeoutMs: 2000 });

  if (document && document !== cachedDoc) {
    setCachedDoc(document);
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isMounted) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isMounted, onClose]);

  if (!isMounted || !cachedDoc) return null;

  const outline = cachedDoc.structuredOutline ?? [];
  const slmDisplay = getSlmDisplayStatus(
    cachedDoc,
    latestEvaluation,
    latestEvalsState,
    targetAgent,
  );
  const humanReadableTitle = getHumanReadableTitle(cachedDoc);

  const handleCopyId = () => {
    if (!cachedDoc?.documentId) return;
    void copy(cachedDoc.documentId);
  };

  const isCopied = Boolean(cachedDoc.documentId && copiedValue === cachedDoc.documentId);

  return (
    <ModuleInspectorDrawerContent
      isOpen={isOpen}
      isAnimating={isAnimating}
      cachedDoc={cachedDoc}
      humanReadableTitle={humanReadableTitle}
      slmDisplay={slmDisplay}
      outline={outline}
      isCopied={isCopied}
      onClose={onClose}
      onCopyId={handleCopyId}
    />
  );
}
