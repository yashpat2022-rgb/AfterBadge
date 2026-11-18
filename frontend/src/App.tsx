import { useEffect, useState } from "react";
import AiComplaintAnalysis from "./AiComplaintAnalysis";

type ComponentStat = { name: string; count: number };
type Complaint = {
  odi_number: string;
  components: string[];
  summary: string;
  date_filed: string;
  source_url: string;
};
type Recall = {
  campaign_number: string;
  component: string;
  summary: string;
  consequence: string;
  remedy: string;
  source_url: string;
};
type PatternExample = {
  odi_number: string;
  matched_phrase: string;
  summary: string;
  source_url: string;
};
type ProblemPattern = {
  key: string;
  title: string;
  description: string;
  count: number;
  odi_numbers: string[];
  examples: PatternExample[];
};
type VehicleSummary = { id: number; make: string; model: string; year: number };
type Vehicle = VehicleSummary & {
  last_synced_at: string | null;
  complaint_count: number;
  recall_count: number;
  top_components: ComponentStat[];
  problem_patterns: ProblemPattern[];
  complaints: Complaint[];
  recalls: Recall[];
};

type ComparisonVehicle = VehicleSummary & {
  last_synced_at: string | null;
  complaint_count: number;
  recall_count: number;
};
type ComponentComparison = {
  name: string;
  left_count: number;
  right_count: number;
};
type Comparison = {
  left: ComparisonVehicle;
  right: ComparisonVehicle;
  component_comparison: ComponentComparison[];
};

type Tab = "problems" | "complaints" | "recalls";

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}

export default function App() {
  const [aiResults, setAiResults] = useState<
    Record<
      string,
      {
        issues: { category: string; evidence: string }[] | null;
        loading: boolean;
        error: string | null;
      }
    >
  >({});

  const [make, setMake] = useState("ACURA");
  const [model, setModel] = useState("RDX");
  const [year, setYear] = useState("2012");
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [history, setHistory] = useState<VehicleSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("problems");
  const [componentFilter, setComponentFilter] = useState("ALL");
  const [patternFilter, setPatternFilter] = useState<string | null>(null);
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState("");

  async function loadHistory() {
    try {
      const response = await fetch("/api/vehicles");
      if (response.ok) setHistory(await response.json());
    } catch {
      /* backend may not be running yet */
    }
  }

  async function analyzeComplaint(odiNumber: string) {
    // Show loading state for this complaint
    setAiResults((previous) => ({
      ...previous,
      [odiNumber]: {
        issues: null,
        loading: true,
        error: null,
      },
    }));

    try {
      // Ask our Python backend to analyze this complaint
      const response = await fetch(
        `/api/complaints/${encodeURIComponent(odiNumber)}/analyze`,
        { method: "POST" },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "AI analysis failed.");
      }

      // Save the AI results for this complaint
      setAiResults((previous) => ({
        ...previous,
        [odiNumber]: {
          issues: data.issues,
          loading: false,
          error: null,
        },
      }));
    } catch (error) {
      // Display an error if something goes wrong
      setAiResults((previous) => ({
        ...previous,
        [odiNumber]: {
          issues: null,
          loading: false,
          error:
            error instanceof Error ? error.message : "Something went wrong.",
        },
      }));
    }
  }

  useEffect(() => {
    void loadHistory();
  }, []);

  async function chooseSaved(id: number) {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/vehicles/${id}`);
      if (!response.ok) throw new Error("Unable to load saved vehicle.");
      const data: Vehicle = await response.json();
      setVehicle(data);
      setMake(data.make);
      setModel(data.model);
      setYear(String(data.year));
      setTab("problems");
      setComponentFilter("ALL");
      setPatternFilter(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams({
        make: make.trim(),
        model: model.trim(),
        year,
      });
      const response = await fetch(`/api/vehicles/sync?${params}`, {
        method: "POST",
      });
      if (!response.ok) {
        let detail = "Unable to retrieve this vehicle from NHTSA.";
        try {
          detail = (await response.json()).detail || detail;
        } catch {
          /* ignore invalid body */
        }
        throw new Error(detail);
      }
      setVehicle(await response.json());
      setComparison(null); // A fresh import may change previously displayed counts.
      setTab("problems");
      setComponentFilter("ALL");
      setPatternFilter(null);
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function compareSaved(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setComparisonError("");
    if (!leftId || !rightId || leftId === rightId) {
      setComparisonError("Choose two different saved vehicles.");
      return;
    }
    setComparisonLoading(true);
    try {
      const params = new URLSearchParams({
        left_id: leftId,
        right_id: rightId,
      });
      const response = await fetch(`/api/compare?${params}`);
      if (!response.ok) {
        let detail = "Could not compare these vehicles.";
        try {
          detail = (await response.json()).detail || detail;
        } catch {
          /* ignore invalid response */
        }
        throw new Error(detail);
      }
      setComparison(await response.json());
    } catch (e) {
      setComparison(null);
      setComparisonError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setComparisonLoading(false);
    }
  }

  const selectedPattern = vehicle?.problem_patterns?.find(
    (p) => p.key === patternFilter,
  );
  const patternIds = selectedPattern
    ? new Set(selectedPattern.odi_numbers)
    : null;
  const complaints = (vehicle?.complaints ?? []).filter(
    (c) =>
      (componentFilter === "ALL" || c.components.includes(componentFilter)) &&
      (!patternIds || patternIds.has(c.odi_number)),
  );
  const maxCount = Math.max(
    1,
    ...(vehicle?.top_components.map((c) => c.count) ?? []),
  );

  return (
    <div className="page">
      <header className="header wrap">
        <div className="logo">
          <span className="logo-mark">a.</span>
          <span>
            after<span className="logo-light">badge.</span>
          </span>
        </div>
        <span className="header-right">
          AUTOMOTIVE PROBLEM INTELLIGENCE <span className="version">v0.3</span>
        </span>
      </header>

      <main className="wrap">
        <section className="hero">
          <div className="eyebrow">
            <span className="green-dot" /> REAL DATA. CLEARER DECISIONS.
          </div>
          <h1>
            Know what goes wrong
            <br />
            <span>before you buy.</span>
          </h1>
          <p className="hero-copy">
            Explore government-reported safety complaints and recalls. Find
            repeated symptom phrases, compare model years, and inspect the
            original source reports.
          </p>
        </section>

        <section className="search-panel" aria-label="Search vehicle">
          <div className="panel-title">
            <span className="section-number">01</span> EXPLORE A VEHICLE
          </div>
          <form className="search-grid" onSubmit={search}>
            <label>
              MAKE
              <input
                value={make}
                onChange={(e) => setMake(e.target.value)}
                required
                maxLength={80}
                placeholder="e.g. BMW"
              />
            </label>
            <label>
              MODEL
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                required
                maxLength={100}
                placeholder="e.g. 330I"
              />
            </label>
            <label>
              MODEL YEAR
              <input
                type="number"
                min="1950"
                max="2035"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                required
              />
            </label>
            <button disabled={loading}>
              {loading ? "Fetching records..." : "Explore vehicle  ↗"}
            </button>
          </form>
          <p className="hint">
            Try ACURA / RDX / 2012 for a small example. Use the official NHTSA
            model naming for best results.
          </p>
          {error && <ErrorMessage message={error} />}
        </section>

        <section
          className="search-panel compare-panel"
          aria-label="Compare vehicles"
        >
          <div className="panel-title">
            <span className="section-number">02</span> COMPARE TWO VEHICLES
          </div>
          <p className="muted">
            Explore and import at least two cars above, then select them below
            to compare their reported problem categories side by side.
          </p>
          <form className="compare-grid" onSubmit={compareSaved}>
            <label>
              VEHICLE A
              <select
                value={leftId}
                onChange={(e) => {
                  setLeftId(e.target.value);
                  setComparison(null);
                }}
                required
              >
                <option value="">Select first vehicle</option>
                {history.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.year} {v.make} {v.model}
                  </option>
                ))}
              </select>
            </label>
            <label>
              VEHICLE B
              <select
                value={rightId}
                onChange={(e) => {
                  setRightId(e.target.value);
                  setComparison(null);
                }}
                required
              >
                <option value="">Select second vehicle</option>
                {history.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.year} {v.make} {v.model}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={
                comparisonLoading ||
                history.length < 2 ||
                !leftId ||
                !rightId ||
                leftId === rightId
              }
            >
              {comparisonLoading ? "Comparing..." : "Compare vehicles ↗"}
            </button>
          </form>
          {history.length < 2 && (
            <p className="hint">
              You need two saved vehicles before comparison becomes available.
            </p>
          )}
          {comparisonError && <ErrorMessage message={comparisonError} />}
        </section>

        {comparison && (
          <section
            className="results comparison-results"
            aria-label="Comparison results"
          >
            <div className="result-header">
              <div>
                <div className="eyebrow">SIDE-BY-SIDE RESEARCH</div>
                <h2>
                  Vehicle <span>comparison</span>
                </h2>
              </div>
            </div>
            <div className="comparison-summary-grid">
              {[comparison.left, comparison.right].map((v, i) => (
                <div className="comparison-summary" key={v.id}>
                  <span className="micro-label">
                    VEHICLE {i === 0 ? "A" : "B"}
                  </span>
                  <h3>
                    {v.year} {v.make} {v.model}
                  </h3>
                  <div className="comparison-stat">
                    <span>Consumer complaints</span>
                    <strong>{v.complaint_count}</strong>
                  </div>
                  <div className="comparison-stat">
                    <span>Recall campaigns</span>
                    <strong>{v.recall_count}</strong>
                  </div>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => void chooseSaved(v.id)}
                  >
                    Inspect original reports ↗
                  </button>
                </div>
              ))}
            </div>
            <div className="content-card">
              <h3 className="comparison-heading">
                Reported component categories
              </h3>
              <p className="muted">
                Counts represent consumer complaints mentioning each category. A
                single complaint may appear in multiple categories. The same
                number of complaints does not mean the same risk of failure.
              </p>
              {comparison.component_comparison.length === 0 ? (
                <p className="muted">
                  Neither vehicle has component-tagged complaints in the
                  imported records.
                </p>
              ) : (
                <div className="compare-table-wrap">
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th scope="col">Component</th>
                        <th scope="col">Vehicle A reports</th>
                        <th scope="col">Vehicle B reports</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.component_comparison.map((row) => (
                        <tr key={row.name}>
                          <th scope="row">{row.name}</th>
                          <td>{row.left_count}</td>
                          <td>{row.right_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="disclaimer">
              <strong>How to interpret this:</strong> These are unadjusted NHTSA
              reports, not comparative failure probabilities, quality ratings,
              or a recommendation to buy one car. Model years can differ in
              vehicle population, time on the road, and reporting behavior.
            </div>
          </section>
        )}

        {history.length > 0 && (
          <div className="history">
            <span className="micro-label">RECENTLY EXPLORED</span>
            {history.slice(0, 6).map((v) => (
              <button key={v.id} onClick={() => void chooseSaved(v.id)}>
                {v.year} {v.make} {v.model} ↗
              </button>
            ))}
          </div>
        )}

        {!vehicle && (
          <div className="empty">
            <div className="empty-icon">⌕</div>
            <h2>Start with a vehicle.</h2>
            <p>
              Enter a make, model and year to import real NHTSA records and
              explore the results.
            </p>
          </div>
        )}

        {vehicle && (
          <section className="results">
            <div className="result-header">
              <div>
                <div className="eyebrow">VEHICLE REPORT</div>
                <h2>
                  {vehicle.year} {vehicle.make} <span>{vehicle.model}</span>
                </h2>
              </div>
              <div className="fresh">
                LAST SYNCED
                <br />
                <strong>
                  {vehicle.last_synced_at
                    ? new Date(vehicle.last_synced_at).toLocaleString()
                    : "Not available"}
                </strong>
              </div>
            </div>
            <div className="metrics">
              <div className="metric">
                <span>OWNER COMPLAINTS</span>
                <strong>{vehicle.complaint_count}</strong>
                <small>Reports in NHTSA dataset</small>
              </div>
              <div className="metric">
                <span>RECALL CAMPAIGNS</span>
                <strong>{vehicle.recall_count}</strong>
                <small>Model-level recall records</small>
              </div>
              <div className="metric">
                <span>REPORTED COMPONENTS</span>
                <strong>{vehicle.top_components.length}</strong>
                <small>Categories mentioned</small>
              </div>
            </div>
            <div className="tabs" role="tablist" aria-label="Report sections">
              <button
                role="tab"
                aria-selected={tab === "problems"}
                className={tab === "problems" ? "active" : ""}
                onClick={() => setTab("problems")}
              >
                Problem patterns
              </button>
              <button
                role="tab"
                aria-selected={tab === "complaints"}
                className={tab === "complaints" ? "active" : ""}
                onClick={() => setTab("complaints")}
              >
                Complaint records
              </button>
              <button
                role="tab"
                aria-selected={tab === "recalls"}
                className={tab === "recalls" ? "active" : ""}
                onClick={() => setTab("recalls")}
              >
                Safety recalls
              </button>
            </div>

            {tab === "problems" && (
              <div className="pattern-layout">
                <div className="content-card">
                  <div className="card-heading">
                    <h3>Potential symptom patterns</h3>
                    <span className="micro-label">EXPLICIT PHRASE MATCHES</span>
                  </div>
                  <p className="muted">
                    Our first detection engine searches complaint narratives for
                    specific phrases. Each match is traceable to its original
                    complaint. These are possible symptom mentions, not verified
                    problems or diagnoses.
                  </p>
                  {!vehicle.problem_patterns ||
                  vehicle.problem_patterns.length === 0 ? (
                    <div className="pattern-empty">
                      No symptom phrases matched our current rules. This does
                      not mean the vehicle has no reported problems. Check the
                      complaint records and component categories below.
                    </div>
                  ) : (
                    <div className="pattern-grid">
                      {vehicle.problem_patterns.map((p) => (
                        <article className="pattern-card" key={p.key}>
                          <div className="pattern-top">
                            <h4>{p.title}</h4>
                            <span className="pattern-count">
                              {p.count} {p.count === 1 ? "report" : "reports"}
                            </span>
                          </div>
                          <p className="muted">{p.description}</p>
                          {p.examples.length > 0 && (
                            <div className="pattern-example">
                              <span className="micro-label">
                                MATCHED PHRASE
                              </span>
                              <p>“{p.examples[0].matched_phrase}”</p>
                              <a
                                href={p.examples[0].source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Original ODI #{p.examples[0].odi_number} ↗
                              </a>
                            </div>
                          )}
                          <button
                            type="button"
                            className="pattern-button"
                            onClick={() => {
                              setPatternFilter(p.key);
                              setComponentFilter("ALL");
                              setTab("complaints");
                            }}
                          >
                            Review {p.count} source{" "}
                            {p.count === 1 ? "report" : "reports"} ↗
                          </button>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
                <div className="content-card">
                  <div className="card-heading">
                    <h3>Reported component categories</h3>
                    <span className="micro-label">NUMBER OF COMPLAINTS</span>
                  </div>
                  <p className="muted">
                    NHTSA component tags, not automatically detected symptoms. A
                    complaint can mention several components; select one to
                    inspect its original report.
                  </p>
                  {vehicle.top_components.length === 0 ? (
                    <p>No reported complaints were returned for this query.</p>
                  ) : (
                    <div className="chart">
                      {vehicle.top_components.slice(0, 14).map((s) => (
                        <button
                          key={s.name}
                          className="barrow"
                          onClick={() => {
                            setComponentFilter(s.name);
                            setPatternFilter(null);
                            setTab("complaints");
                          }}
                        >
                          <span className="barlabel">{s.name}</span>
                          <span className="bar-track">
                            <span
                              className="bar-fill"
                              style={{
                                width: `${(s.count / maxCount) * 100}%`,
                              }}
                            />
                          </span>
                          <strong>{s.count}</strong>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {tab === "complaints" && (
              <div className="content-card">
                <div className="card-heading">
                  <h3>Original owner complaints</h3>
                  <select
                    aria-label="Filter by component"
                    value={componentFilter}
                    onChange={(e) => setComponentFilter(e.target.value)}
                  >
                    <option value="ALL">All components</option>
                    {vehicle.top_components.map((s) => (
                      <option key={s.name}>{s.name}</option>
                    ))}
                  </select>
                </div>
                {selectedPattern && (
                  <div className="filter-chip">
                    <span>
                      Showing phrase matches:{" "}
                      <strong>{selectedPattern.title}</strong>
                    </span>
                    <button
                      type="button"
                      onClick={() => setPatternFilter(null)}
                    >
                      Clear pattern filter ×
                    </button>
                  </div>
                )}
                <p className="muted">
                  Showing {Math.min(complaints.length, 150)} of{" "}
                  {complaints.length} matching complaint records. Reports are
                  allegations submitted by consumers, not verified defects or
                  failure rates.
                </p>
                <div className="records">
                  {complaints.slice(0, 150).map((c) => (
                    <article className="record" key={c.odi_number}>
                      <div className="record-top">
                        <strong>ODI #{c.odi_number}</strong>
                        <span>{c.date_filed || "Date unavailable"}</span>
                      </div>
                      <div className="tags">
                        {c.components.map((name) => (
                          <span className="tag" key={name}>
                            {name}
                          </span>
                        ))}
                      </div>
                      <p>{c.summary || "No description provided."}</p>
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View original NHTSA record ↗
                      </a>

                      <button
                        type="button"
                        onClick={() => analyzeComplaint(c.odi_number)}
                        disabled={Boolean(
                          aiResults[c.odi_number]?.loading ||
                          aiResults[c.odi_number]?.issues,
                        )}
                      >
                        {aiResults[c.odi_number]?.loading
                          ? "✨ Analyzing..."
                          : "✨ Analyze with AI"}
                      </button>

                      <AiComplaintAnalysis
                        issues={aiResults[c.odi_number]?.issues ?? null}
                        loading={aiResults[c.odi_number]?.loading ?? false}
                        error={aiResults[c.odi_number]?.error ?? null}
                      />
                    </article>
                  ))}
                </div>
                {complaints.length > 150 && (
                  <p className="muted">
                    Only the first 150 matching records are displayed.
                    Pagination is planned for a later release.
                  </p>
                )}
              </div>
            )}

            {tab === "recalls" && (
              <div className="content-card">
                <div className="card-heading">
                  <h3>Official recall campaigns</h3>
                  <span className="micro-label">
                    {vehicle.recall_count} FOUND
                  </span>
                </div>
                {vehicle.recalls.length === 0 && (
                  <p className="muted">
                    No recalls were returned for this make/model/year. Check
                    NHTSA directly for VIN-specific status.
                  </p>
                )}
                <div className="records">
                  {vehicle.recalls.map((r) => (
                    <article className="record" key={r.campaign_number}>
                      <div className="record-top">
                        <strong>Campaign #{r.campaign_number}</strong>
                      </div>
                      <div className="tags">
                        <span className="tag">
                          {r.component || "Component not listed"}
                        </span>
                      </div>
                      <p>{r.summary}</p>
                      {r.consequence && (
                        <p>
                          <b>Potential consequence:</b> {r.consequence}
                        </p>
                      )}
                      {r.remedy && (
                        <p>
                          <b>Remedy:</b> {r.remedy}
                        </p>
                      )}
                      <a
                        href={r.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View official campaign ↗
                      </a>
                    </article>
                  ))}
                </div>
              </div>
            )}
            <div className="disclaimer">
              <strong>Important context:</strong> Complaint counts do not
              measure a vehicle's actual reliability or defect probability.
              Reports are voluntary and affected by reporting patterns, vehicle
              populations and age. Recall results shown are model-level;
              VIN-specific recall status must be checked through NHTSA.
            </div>
          </section>
        )}
      </main>
      <footer className="footer wrap">
        <span>AfterBadge · Educational portfolio project</span>
        <span>
          Source:{" "}
          <a
            href="https://www.nhtsa.gov/nhtsa-datasets-and-apis"
            target="_blank"
            rel="noopener noreferrer"
          >
            NHTSA Open Data ↗
          </a>{" "}
          · Not affiliated with NHTSA
        </span>
      </footer>
    </div>
  );
}
