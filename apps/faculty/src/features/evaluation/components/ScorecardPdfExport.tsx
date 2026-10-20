import { useState } from "react";
import { DownloadSimple } from "@phosphor-icons/react";
import type { EvaluationResultsResponse } from "../types";
import { exportScorecardPdf } from "../utils/scorecardPdf";

type ScorecardPdfExportProps = {
  results: EvaluationResultsResponse;
};

export function ScorecardPdfExport({ results }: ScorecardPdfExportProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setErrorMessage(null);
    try {
      await exportScorecardPdf(results);
    } catch (error) {
      console.error("Unable to create the evaluation scorecard PDF.", error);
      setErrorMessage("PDF export failed. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        className="inline-flex h-9 items-center justify-center rounded-sm bg-primary px-4 text-xs font-semibold uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-wait disabled:opacity-70"
        onClick={handleExport}
        disabled={isExporting}
      >
        <DownloadSimple className="mr-1.5 size-4" aria-hidden="true" />
        {isExporting ? "Creating PDF..." : "Export Scorecard PDF"}
      </button>
      {errorMessage && (
        <span className="text-xs font-medium text-destructive" role="alert">
          {errorMessage}
        </span>
      )}
    </div>
  );
}
