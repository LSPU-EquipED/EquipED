import { useState } from "react";
import { Pause, Play } from "@phosphor-icons/react";
import queued from "../../../../assets/animations/workspace/queued.svg?raw";
import preparation from "../../../../assets/animations/workspace/preparation.svg?raw";
import review from "../../../../assets/animations/workspace/specialist-review.svg?raw";
import finalizing from "../../../../assets/animations/workspace/finalizing.svg?raw";
import type { ActiveStage } from "../../utils/evaluationProgress";
import moduleDossier from "../../../../assets/illustrations/specialists/workspace/module-dossier.svg";

const artwork: Record<ActiveStage, string> = {
  SUBMITTED: queued,
  PREPROCESSING: preparation,
  EVALUATING: review,
  SYNTHESIZING: finalizing,
};

export function StageArtwork({ stage }: { stage?: ActiveStage }) {
  const [paused, setPaused] = useState(false);
  return (
    <div className={`swp-progress-art${paused ? " is-paused" : ""}`}>
      {/* Only trusted repository SVGs are inlined so their CSS motion can pause. */}
      {stage ? (
        <div
          key={stage}
          className="swp-stage-artwork"
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: artwork[stage] }}
        />
      ) : (
        <img
          className="swp-stage-static"
          src={moduleDossier}
          alt=""
          aria-hidden="true"
        />
      )}
      {stage && (
        <button
          type="button"
          className="swp-motion-toggle"
          onClick={() => setPaused(!paused)}
          aria-pressed={paused}
          aria-label={paused ? "Resume animation" : "Pause animation"}
        >
          {paused ? (
            <Play size={13} aria-hidden="true" />
          ) : (
            <Pause size={13} aria-hidden="true" />
          )}
          {paused ? "Resume motion" : "Pause motion"}
        </button>
      )}
    </div>
  );
}
