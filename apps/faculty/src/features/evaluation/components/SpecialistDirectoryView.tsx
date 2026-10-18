import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { TargetAgent } from "@equiped/types";
import type { DeskQueueItem } from "../types";
import { SelectModuleModal } from "./SelectModuleModal";
import { WorkspaceLanding } from "./workspace/WorkspaceLanding";

export interface SpecialistDirectoryViewProps {
  validAgent: TargetAgent;
  items: DeskQueueItem[];
}
export function SpecialistDirectoryView({
  validAgent,
  items,
}: SpecialistDirectoryViewProps) {
  const [selecting, setSelecting] = useState(false);
  const navigate = useNavigate();
  return (
    <>
      <WorkspaceLanding
        agent={validAgent}
        items={items}
        onSelect={() => setSelecting(true)}
        onOpen={(item) =>
          void navigate({
            to: "/specialists/$agentId/$documentId",
            params: { agentId: validAgent, documentId: item.document_id },
          })
        }
        onLibrary={() => void navigate({ to: "/documents" })}
      />
      {selecting && (
        <SelectModuleModal
          agentId={validAgent}
          items={items}
          onClose={() => setSelecting(false)}
        />
      )}
    </>
  );
}
