import { useEffect, useState } from "react";
import type { FormEvent } from "react";

export type VehicleSelection = { year: string; make: string; model: string };

type VehicleSearchProps = {
  selection: VehicleSelection;
  onChange: (selection: VehicleSelection) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
};

type OptionResult = {
  key: string;
  options: string[];
  error: boolean;
  incomplete: boolean;
};

function useVehicleOptions(url: string | null, attempt: number) {
  const [result, setResult] = useState<OptionResult | null>(null);
  const key = url === null ? "" : url + "#" + attempt;

  useEffect(() => {
    if (url === null) return;
    const controller = new AbortController();

    async function load(requestUrl: string) {
      try {
        const response = await fetch(requestUrl, { signal: controller.signal });
        if (!response.ok) throw new Error("Could not load vehicle options.");
        const data = await response.json();
        if (!controller.signal.aborted) {
          setResult({ key, options: data.options, error: false, incomplete: data.incomplete === true });
        }
      } catch {
        if (!controller.signal.aborted) {
          setResult({ key, options: [], error: true, incomplete: false });
        }
      }
    }

    void load(url);
    return () => controller.abort();
  }, [key, url]);

  if (url !== null && result?.key === key) return { ...result, loading: false };
  return { options: [], error: false, incomplete: false, loading: url !== null };
}

function includeSelection(options: string[], selection: string) {
  return selection && !options.includes(selection) ? [selection, ...options] : options;
}

export default function VehicleSearch({
  selection, onChange, onSearch, submitting,
}: VehicleSearchProps) {
  const { year, make, model } = selection;
  const [attempt, setAttempt] = useState(0);
  const endpoint = "/api/vehicle-options";
  const yearQuery = new URLSearchParams({ year });
  const modelQuery = new URLSearchParams({ year, make });
  const years = useVehicleOptions(endpoint, attempt);
  const makes = useVehicleOptions(year ? endpoint + "?" + yearQuery : null, attempt);
  const models = useVehicleOptions(year && make ? endpoint + "?" + modelQuery : null, attempt);
  const hasError = years.error || makes.error || models.error;
  const incomplete = makes.incomplete || models.incomplete;

  return (
    <>
      <form className="search-grid" onSubmit={onSearch}>
        <label>
          YEAR
          <select
            value={year}
            onChange={(event) => onChange({ year: event.target.value, make: "", model: "" })}
            disabled={submitting || years.loading || (years.options.length === 0 && !year)}
            required
          >
            <option value="">{years.loading ? "Loading years…" : "Choose a year"}</option>
            {includeSelection(years.options, year).map((option) => <option key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          MAKE
          <select
            value={make}
            onChange={(event) => onChange({ year, make: event.target.value, model: "" })}
            disabled={submitting || !year || makes.loading || (makes.options.length === 0 && !make)}
            required
          >
            <option value="">
              {!year ? "Choose a year first" : makes.loading ? "Loading makes…" :
                makes.options.length || make ? "Choose a make" : "No makes available"}
            </option>
            {includeSelection(makes.options, make).map((option) => <option key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          MODEL
          <select
            value={model}
            onChange={(event) => onChange({ year, make, model: event.target.value })}
            disabled={submitting || !make || models.loading || (models.options.length === 0 && !model)}
            required
          >
            <option value="">
              {!make ? "Choose a make first" : models.loading ? "Loading models…" :
                models.options.length || model ? "Choose a model" : "No models available"}
            </option>
            {includeSelection(models.options, model).map((option) => <option key={option}>{option}</option>)}
          </select>
        </label>
        <button disabled={submitting || !year || !make || !model}>
          {submitting ? "Loading reports…" : "View reports"}
        </button>
      </form>
      <p className="hint">
        NHTSA may list reports under the trim or the model family, such as 330I or 3 SERIES.
      </p>
      {(hasError || incomplete) && (
        <div className="vehicle-options-notice" role="status">
          {hasError ? "Could not load vehicle options." : "Some vehicle options may be missing."}
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>
      )}
    </>
  );
}
