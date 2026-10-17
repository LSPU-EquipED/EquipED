import { useState } from "react";
import { usePresence } from "@equiped/ui";
import type { ClientDocument } from "@equiped/types";
import { getHumanReadableTitle } from "../utils/moduleInspector.utils";
import { useStorageDialog } from "../hooks/useStorageDialog";
import { useClipboardCopy } from "../hooks/useClipboardCopy";
import { ModuleInspectorDrawerContent } from "./ModuleInspectorDrawerContent";

export interface ModuleInspectorDrawerProps {
  document: ClientDocument | null;
  onClose: () => void;
}

export function ModuleInspectorDrawer({
  document,
  onClose,
}: ModuleInspectorDrawerProps) {
  const isOpen = Boolean(document);
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 240 });
  const [cachedDoc, setCachedDoc] = useState<ClientDocument | null>(document);
  const { copiedValue, copy } = useClipboardCopy({ resetTimeoutMs: 2000 });

  if (document && document !== cachedDoc) {
    setCachedDoc(document);
  }

  const dialogRef = useStorageDialog({ isOpen, isMounted, onClose });

  if (!isMounted || !cachedDoc) return null;

  const outline = cachedDoc.structuredOutline ?? [];
  const humanReadableTitle = getHumanReadableTitle(cachedDoc);

  const handleCopyId = () => {
    if (!cachedDoc?.documentId) return;
    void copy(cachedDoc.documentId);
  };

  const isCopied = Boolean(
    cachedDoc.documentId && copiedValue === cachedDoc.documentId,
  );

  return (
    <ModuleInspectorDrawerContent
      dialogRef={dialogRef}
      isOpen={isOpen}
      isAnimating={isAnimating}
      cachedDoc={cachedDoc}
      humanReadableTitle={humanReadableTitle}
      outline={outline}
      isCopied={isCopied}
      onClose={onClose}
      onCopyId={handleCopyId}
    />
  );
}
