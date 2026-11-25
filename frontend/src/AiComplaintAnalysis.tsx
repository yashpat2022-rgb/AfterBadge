type AiIssue = {
  category: string;
  evidence: string;
  component?: string;
};

export type ComplaintAnalysis =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; issues: AiIssue[]; expanded: boolean };

type AiComplaintAnalysisProps = {
  odiNumber: string;
  sourceUrl: string;
  analysis?: ComplaintAnalysis;
  onAnalyze: () => void;
};

export default function AiComplaintAnalysis({
  odiNumber,
  sourceUrl,
  analysis,
  onAnalyze,
}: AiComplaintAnalysisProps) {
  const panelId = `complaint-analysis-${odiNumber}`;
  const expanded = Boolean(analysis && (analysis.status !== "ready" || analysis.expanded));
  let buttonLabel = "Analyze with AI";
  if (analysis?.status === "loading") buttonLabel = "Analyzing…";
  if (analysis?.status === "error") buttonLabel = "Retry analysis";
  if (analysis?.status === "ready") {
    buttonLabel = expanded ? "Hide analysis" : "Show analysis";
  }

  return (
    <>
      <div className="complaint-actions">
        <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
          View original NHTSA record ↗
        </a>
        <button
          type="button"
          className="complaint-ai-button"
          onClick={onAnalyze}
          aria-controls={panelId}
          aria-expanded={expanded}
          aria-disabled={analysis?.status === "loading" || undefined}
          aria-label={`${buttonLabel} for ODI ${odiNumber}`}
        >
          {buttonLabel}
        </button>
      </div>

      <div id={panelId} className="ai-analysis" hidden={!expanded} aria-live="polite">
        {analysis?.status === "loading" && <p>Looking for symptoms in this report…</p>}
        {analysis?.status === "error" && <p>{analysis.message}</p>}
        {analysis?.status === "ready" && (
          <>
            <h4>AI analysis</h4>
            {analysis.issues.length === 0 ? (
              <p>No clear symptoms found in this report.</p>
            ) : (
              <>
                <ul className="ai-issues">
                  {analysis.issues.map(({ category, component, evidence }, index) => (
                    <li key={index}>
                      <div className="ai-issue-header">
                        <strong>{category.replace(/_/g, " ")}</strong>
                        <span>{component && component !== "unknown"
                          ? `AI part: ${component.replace(/_/g, " ")}`
                          : "AI part unknown"}</span>
                      </div>
                      <blockquote>“{evidence}”</blockquote>
                    </li>
                  ))}
                </ul>
                <p className="ai-analysis-note">AI labels describe the reported symptoms. The cause remains unverified.</p>
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}
