import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import type { ClientDocument, TargetAgent } from '@equiped/types';
import { EvaluationConfirmModal } from '@/features/evaluation/components/EvaluationConfirmModal';
import { FacultyHome } from '@/features/home/components/FacultyHome';

export function FacultyHomePage() {
  const navigate = useNavigate();
  const [evaluatingTarget, setEvaluatingTarget] = useState<{
    doc: ClientDocument;
    agent: TargetAgent;
  } | null>(null);

  return (
    <>
      <FacultyHome onEvaluate={(doc, agent) => setEvaluatingTarget({ doc, agent })} />
      {evaluatingTarget && (
        <EvaluationConfirmModal
          documentId={evaluatingTarget.doc.documentId}
          documentTitle={evaluatingTarget.doc.title}
          detectedProgram={evaluatingTarget.doc.program ?? null}
          targetAgent={evaluatingTarget.agent}
          onClose={() => setEvaluatingTarget(null)}
          onSubmitted={() => {
            const target = evaluatingTarget;
            setEvaluatingTarget(null);
            void navigate({
              to: '/specialists/$agentId/$documentId',
              params: {
                agentId: target.agent,
                documentId: target.doc.documentId,
              },
            });
          }}
        />
      )}
    </>
  );
}
