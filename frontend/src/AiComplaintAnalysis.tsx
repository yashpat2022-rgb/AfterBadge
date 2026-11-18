
type AiIssue = {
  category: string;
  evidence: string;
};

type AiComplaintAnalysisProps = {
  issues: AiIssue[] | null;
  loading: boolean;
  error: string | null;
};

export default function AiComplaintAnalysis({
  issues,
  loading,
  error,
}: AiComplaintAnalysisProps) {
  // Show a message while Gemini is analyzing
  if (loading) {
    return (
      <div className="ai-analysis">
        <p>✨ Gemini is analyzing this complaint...</p>
      </div>
    );
  }

  // Show an error if analysis fails
  if (error) {
    return (
      <div className="ai-analysis">
        <p>Unable to analyze this complaint: {error}</p>
      </div>
    );
  }

  // Nothing to display before analysis
  if (issues === null) {
    return null;
  }

  // Handle complaints with no detected symptoms
  if (issues.length === 0) {
    return (
      <div className="ai-analysis">
        <h4>✨ AI Analysis</h4>
        <p>No clear symptoms were identified.</p>
      </div>
    );
  }

  // Display the issues Gemini identified
  return (
    <div className="ai-analysis">
      <h4>✨ Gemini AI Analysis</h4>

      <p>
        Potential issues mentioned in this complaint:
      </p>

      {issues.map((issue, index) => (
        <div className="ai-issue" key={index}>
          <strong>
            {issue.category.replace(/_/g, " ")}
          </strong>

          <p>
            <strong>Evidence:</strong> "{issue.evidence}"
          </p>
        </div>
      ))}

      <p className="muted">
        AI-generated interpretation of an owner report.
        These are not verified vehicle defects.
      </p>
    </div>
  );
}
